"""Conversation and Learning Loop application service."""

from __future__ import annotations

import hashlib
from typing import Any

from backend.app.ai.core_adapter import AICorePort
from backend.app.ai.result_mapper import action_payloads
from backend.app.errors import InvalidActionError
from backend.app.models import CoreInvocation, TurnOutcome, TurnRecord
from backend.app.persistence.memory import MemoryRepository
from backend.app.retrieval.local_slides import LocalSlideRepository


class TurnService:
    """Own state transitions; HTTP handlers remain thin transport adapters."""

    def __init__(
        self,
        repository: MemoryRepository,
        ai_core: AICorePort,
        slides: LocalSlideRepository,
    ):
        self.repository = repository
        self.ai_core = ai_core
        self.slides = slides

    async def create_conversation(self, owner_id: str, course_id: str = "default"):
        return await self.repository.create_conversation(owner_id, course_id)

    async def conversation_snapshot(self, owner_id: str, conversation_id: str):
        return await self.repository.snapshot(conversation_id, owner_id)

    async def start_turn(
        self,
        *,
        owner_id: str,
        conversation_id: str,
        question: str,
        selected_text: str,
        page_number: int,
        conversation_history: list[dict[str, Any]],
        deck_id: str = "d1",
        idempotency_key: str | None = None,
    ) -> TurnOutcome:
        payload = {
            "conversation_id": conversation_id,
            "question": question,
            "selected_text": selected_text,
            "page_number": page_number,
            "deck_id": deck_id,
        }
        if idempotency_key:
            existing = await self.repository.get_idempotent(
                owner_id, idempotency_key, payload
            )
            if existing:
                return existing

        conversation = await self.repository.get_conversation(conversation_id, owner_id)
        async with self.repository.conversation_lock(conversation_id):
            if idempotency_key:
                existing = await self.repository.get_idempotent(
                    owner_id, idempotency_key, payload
                )
                if existing:
                    return existing
            pending = await self.repository.pending_action_for_conversation(
                conversation_id, owner_id
            )
            if pending is not None:
                await self.repository.abandon_action(pending)

            turn = await self.repository.create_turn(
                conversation, question, page_number, deck_id
            )
            await self.repository.save_message(conversation, turn, "user", question)
            context = self.slides.build_context(
                page_number=page_number,
                deck_id=deck_id,
                selected_text=selected_text,
                query=question,
                recent_history=conversation_history,
            )
            invocation = await self.ai_core.start_turn(
                thread_id=turn.ai_thread_id,
                question=question,
                selected_context=context,
                conversation_history=conversation_history,
            )
            outcome = await self._persist_invocation(
                conversation=conversation,
                turn=turn,
                invocation=invocation,
                page_number=page_number,
                deck_id=deck_id,
            )
            if idempotency_key:
                await self.repository.save_idempotent(
                    owner_id, idempotency_key, payload, outcome
                )
        return outcome

    async def respond(
        self,
        *,
        owner_id: str,
        turn_id: str,
        action_id: str,
        value: str,
        idempotency_key: str,
    ) -> TurnOutcome:
        payload = {"turn_id": turn_id, "action_id": action_id, "value": value}
        existing = await self.repository.get_idempotent(
            owner_id, idempotency_key, payload
        )
        if existing:
            return existing

        action = await self.repository.get_action(action_id, owner_id)
        turn = await self.repository.get_turn(turn_id, owner_id)
        if action.turn_id != turn.id:
            raise InvalidActionError()

        conversation = await self.repository.get_conversation(
            turn.conversation_id, owner_id
        )
        async with self.repository.conversation_lock(conversation.id):
            existing = await self.repository.get_idempotent(
                owner_id, idempotency_key, payload
            )
            if existing:
                return existing
            if action.status != "pending":
                raise InvalidActionError()
            invocation = await self.ai_core.resume_turn(
                thread_id=turn.ai_thread_id, student_input=value
            )
            check_attempt = None
            if action.type in {"multiple_choice", "short_answer"}:
                evaluation = self._check_evaluation(action, value, invocation)
                check_attempt = await self.repository.save_attempt(
                    action=action,
                    answer=value,
                    is_correct=evaluation["is_correct"],
                    score=evaluation.get("score"),
                    misconception_code=evaluation.get("misconception_code"),
                )
            await self.repository.complete_action(action)
            outcome = await self._persist_invocation(
                conversation=conversation,
                turn=turn,
                invocation=invocation,
                page_number=turn.page_number,
                deck_id=turn.deck_id,
                previous_action=action,
                check_attempt=check_attempt,
            )
            await self.repository.save_idempotent(
                owner_id, idempotency_key, payload, outcome
            )
        return outcome

    async def legacy_ask(
        self,
        *,
        owner_id: str,
        conversation_id: str | None,
        question: str,
        selected_text: str,
        page_number: int,
        chat_history: list[dict[str, Any]],
        deck_id: str = "d1",
    ) -> TurnOutcome:
        if conversation_id is None:
            conversation = await self.create_conversation(owner_id)
            conversation_id = conversation.id
        else:
            await self.repository.get_conversation(conversation_id, owner_id)

        pending = await self.repository.pending_action_for_conversation(
            conversation_id, owner_id
        )
        if pending and pending.type == "clarification":
            digest = hashlib.sha256(question.encode()).hexdigest()[:24]
            return await self.respond(
                owner_id=owner_id,
                turn_id=pending.turn_id,
                action_id=pending.id,
                value=question,
                idempotency_key=f"legacy-clar-{pending.id}-{digest}",
            )

        return await self.start_turn(
            owner_id=owner_id,
            conversation_id=conversation_id,
            question=question,
            selected_text=selected_text,
            page_number=page_number,
            deck_id=deck_id,
            conversation_history=chat_history,
        )

    async def _persist_invocation(
        self,
        *,
        conversation,
        turn: TurnRecord,
        invocation: CoreInvocation,
        page_number: int,
        deck_id: str = "d1",
        previous_action=None,
        check_attempt=None,
    ) -> TurnOutcome:
        result = invocation.result
        action_data = action_payloads(result, invocation.state)
        action = None
        if action_data:
            action_type, public_payload, private_payload = action_data
            action = await self.repository.save_action(
                conversation,
                turn,
                action_type,
                public_payload,
                private_payload,
            )

        status = (
            "awaiting_response" if action else str(result.get("status") or "completed")
        )
        await self.repository.update_turn(turn, result, status)
        message = str(result.get("assistant_message") or "")
        if message:
            await self.repository.save_message(conversation, turn, "assistant", message)
        return TurnOutcome(
            conversation=conversation,
            turn=turn,
            result=result,
            action=action,
            page_number=page_number,
            deck_id=deck_id,
            check_attempt=check_attempt,
            previous_action=previous_action,
        )

    @staticmethod
    def _check_evaluation(action, value: str, invocation: CoreInvocation):
        state_evaluation = (
            invocation.state.get("check_result")
            or invocation.state.get("last_check_result")
            or {}
        )
        if state_evaluation:
            return {
                "is_correct": bool(state_evaluation.get("is_correct")),
                "score": state_evaluation.get("score"),
                "misconception_code": state_evaluation.get("misconception_code"),
            }

        correct_option = action.private_payload.get("correct_option_id")
        if correct_option:
            is_correct = value.strip().lower() == str(correct_option).strip().lower()
        else:
            is_correct = bool(invocation.result.get("followups"))

        return {
            "is_correct": is_correct,
            "score": 1.0 if is_correct else 0.0,
            "misconception_code": None if is_correct else "concept_confusion",
        }
