"""Versioned public API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from backend.app.ai.result_mapper import public_action, to_turn_response
from backend.app.schemas.api import (
    ActionRespondRequest,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationSnapshotResponse,
    TurnCreateRequest,
    TurnResponse,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])


def _service(request: Request):
    return request.app.state.turn_service


def _owner(request: Request) -> str:
    return request.state.owner_id


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request):
    service = _service(request)
    is_ready = service.ai_core.available and service.ai_core.configured
    return {
        "status": "ready" if is_ready else "degraded",
        "ai_core_loaded": service.ai_core.available,
        "model_key_configured": service.ai_core.configured,
        "slide_count": len(request.app.state.slide_repository.slides),
    }


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreateRequest, request: Request
) -> ConversationResponse:
    record = await _service(request).create_conversation(
        _owner(request), payload.course_id
    )
    return ConversationResponse(
        conversation_id=record.id,
        status=record.status,
        course_id=record.course_id,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationSnapshotResponse,
)
async def get_conversation(
    conversation_id: str, request: Request
) -> ConversationSnapshotResponse:
    snapshot = await _service(request).conversation_snapshot(
        _owner(request), conversation_id
    )
    conversation = snapshot["conversation"]
    messages = [
        {
            "id": message.id,
            "turn_id": message.turn_id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        for message in snapshot["messages"]
    ]
    turns: list[dict[str, Any]] = [
        {
            "id": turn.id,
            "status": turn.status,
            "route": turn.route,
            "page_number": turn.page_number,
            "deck_id": turn.deck_id,
            "created_at": turn.created_at.isoformat(),
        }
        for turn in snapshot["turns"]
    ]
    return ConversationSnapshotResponse(
        conversation_id=conversation.id,
        status=conversation.status,
        course_id=conversation.course_id,
        messages=messages,
        turns=turns,
        pending_action=public_action(snapshot["pending_action"]),
    )


@router.post(
    "/conversations/{conversation_id}/turns",
    response_model=TurnResponse,
    status_code=201,
)
async def create_turn(
    conversation_id: str, payload: TurnCreateRequest, request: Request
) -> TurnResponse:
    outcome = await _service(request).start_turn(
        owner_id=_owner(request),
        conversation_id=conversation_id,
        question=payload.question,
        selected_text=payload.selected_text,
        page_number=payload.page_number,
        deck_id=payload.deck_id,
        conversation_history=payload.conversation_history,
        idempotency_key=payload.idempotency_key,
    )
    return to_turn_response(outcome, request.state.request_id)


@router.post("/turns/{turn_id}/responses", response_model=TurnResponse)
async def respond_to_action(
    turn_id: str, payload: ActionRespondRequest, request: Request
) -> TurnResponse:
    outcome = await _service(request).respond(
        owner_id=_owner(request),
        turn_id=turn_id,
        action_id=payload.action_id,
        value=payload.value,
        idempotency_key=payload.idempotency_key,
    )
    return to_turn_response(outcome, request.state.request_id)
