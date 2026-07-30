"""In-memory repositories behind an interface suitable for Phase 2 replacement."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections import defaultdict
from typing import Any

from backend.app.errors import ConflictError, ResourceNotFoundError
from backend.app.models import (
    CheckAttemptRecord,
    ConversationRecord,
    MessageRecord,
    PendingActionRecord,
    TurnOutcome,
    TurnRecord,
    utc_now,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class MemoryRepository:
    """Process-local Phase 1 store; all callers use methods replaceable by PostgreSQL."""

    def __init__(self):
        self.conversations: dict[str, ConversationRecord] = {}
        self.turns: dict[str, TurnRecord] = {}
        self.messages: dict[str, MessageRecord] = {}
        self.actions: dict[str, PendingActionRecord] = {}
        self.attempts: dict[str, CheckAttemptRecord] = {}
        self.idempotency: dict[tuple[str, str], tuple[str, TurnOutcome]] = {}
        self._guard = asyncio.Lock()
        self._conversation_locks: defaultdict[str, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )

    def conversation_lock(self, conversation_id: str) -> asyncio.Lock:
        return self._conversation_locks[conversation_id]

    async def create_conversation(
        self, owner_id: str, course_id: str = "default"
    ) -> ConversationRecord:
        record = ConversationRecord(
            id=_new_id("conv"), owner_id=owner_id, course_id=course_id
        )
        async with self._guard:
            self.conversations[record.id] = record
        return record

    async def get_conversation(
        self, conversation_id: str, owner_id: str
    ) -> ConversationRecord:
        record = self.conversations.get(conversation_id)
        if record is None or record.owner_id != owner_id:
            raise ResourceNotFoundError()
        return record

    async def create_turn(
        self,
        conversation: ConversationRecord,
        user_query: str,
        page_number: int,
    ) -> TurnRecord:
        turn = TurnRecord(
            id=_new_id("turn"),
            conversation_id=conversation.id,
            ai_thread_id=_new_id("ai"),
            user_query=user_query,
            page_number=page_number,
        )
        async with self._guard:
            self.turns[turn.id] = turn
            conversation.turn_ids.append(turn.id)
            conversation.updated_at = utc_now()
        return turn

    async def get_turn(self, turn_id: str, owner_id: str) -> TurnRecord:
        turn = self.turns.get(turn_id)
        if turn is None:
            raise ResourceNotFoundError()
        await self.get_conversation(turn.conversation_id, owner_id)
        return turn

    async def save_message(
        self,
        conversation: ConversationRecord,
        turn: TurnRecord,
        role: str,
        content: str,
    ) -> MessageRecord:
        message = MessageRecord(
            id=_new_id("msg"),
            conversation_id=conversation.id,
            turn_id=turn.id,
            role=role,
            content=content,
        )
        async with self._guard:
            self.messages[message.id] = message
            conversation.message_ids.append(message.id)
            conversation.updated_at = utc_now()
        return message

    async def update_turn(
        self, turn: TurnRecord, result: dict[str, Any], status: str
    ) -> None:
        async with self._guard:
            turn.raw_result = result
            turn.route = (result.get("route") or {}).get("name")
            turn.status = status
            turn.updated_at = utc_now()

    async def save_action(
        self,
        conversation: ConversationRecord,
        turn: TurnRecord,
        action_type: str,
        public_payload: dict[str, Any],
        private_payload: dict[str, Any],
    ) -> PendingActionRecord:
        action = PendingActionRecord(
            id=_new_id("action"),
            conversation_id=conversation.id,
            turn_id=turn.id,
            type=action_type,
            public_payload=public_payload,
            private_payload=private_payload,
        )
        async with self._guard:
            self.actions[action.id] = action
        return action

    async def get_action(self, action_id: str, owner_id: str) -> PendingActionRecord:
        action = self.actions.get(action_id)
        if action is None:
            raise ResourceNotFoundError()
        await self.get_conversation(action.conversation_id, owner_id)
        return action

    async def pending_action_for_conversation(
        self, conversation_id: str, owner_id: str
    ) -> PendingActionRecord | None:
        await self.get_conversation(conversation_id, owner_id)
        matches = [
            action
            for action in self.actions.values()
            if action.conversation_id == conversation_id and action.status == "pending"
        ]
        return max(matches, key=lambda item: item.created_at) if matches else None

    async def complete_action(self, action: PendingActionRecord) -> None:
        async with self._guard:
            if action.status != "pending":
                raise ConflictError("Action was already completed.")
            action.status = "completed"
            action.completed_at = utc_now()

    async def save_attempt(
        self,
        action: PendingActionRecord,
        answer: str,
        is_correct: bool,
        score: float | None,
        misconception_code: str | None,
    ) -> CheckAttemptRecord:
        attempt = CheckAttemptRecord(
            id=_new_id("attempt"),
            action_id=action.id,
            turn_id=action.turn_id,
            answer=answer,
            is_correct=is_correct,
            score=score,
            misconception_code=misconception_code,
        )
        async with self._guard:
            self.attempts[attempt.id] = attempt
        return attempt

    async def get_idempotent(
        self, owner_id: str, key: str, payload: dict[str, Any]
    ) -> TurnOutcome | None:
        stored = self.idempotency.get((owner_id, key))
        if stored is None:
            return None
        expected_hash, outcome = stored
        if expected_hash != self._payload_hash(payload):
            raise ConflictError("Idempotency key was reused with a different payload.")
        return outcome

    async def save_idempotent(
        self,
        owner_id: str,
        key: str,
        payload: dict[str, Any],
        outcome: TurnOutcome,
    ) -> None:
        async with self._guard:
            self.idempotency[(owner_id, key)] = (
                self._payload_hash(payload),
                outcome,
            )

    async def snapshot(self, conversation_id: str, owner_id: str) -> dict[str, Any]:
        conversation = await self.get_conversation(conversation_id, owner_id)
        pending = await self.pending_action_for_conversation(conversation_id, owner_id)
        messages = [
            self.messages[message_id] for message_id in conversation.message_ids
        ]
        turns = [self.turns[turn_id] for turn_id in conversation.turn_ids]
        return {
            "conversation": conversation,
            "messages": messages,
            "turns": turns,
            "pending_action": pending,
        }

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(encoded).hexdigest()
