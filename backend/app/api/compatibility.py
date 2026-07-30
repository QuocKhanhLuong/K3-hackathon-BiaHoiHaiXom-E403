"""Compatibility routes consumed by the existing static frontend."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from backend.app.ai.result_mapper import public_citations, suggestions
from backend.app.errors import AIServiceError, BackendError, InvalidActionError
from backend.app.models import TurnOutcome
from backend.app.schemas.api import (
    LegacyAskRequest,
    LegacyClarificationRequest,
    LegacyQuizRequest,
)

router = APIRouter(tags=["frontend-compatibility"])


def _service(request: Request):
    return request.app.state.turn_service


def _slides(request: Request):
    return request.app.state.slide_repository


def _owner(request: Request) -> str:
    return request.state.owner_id


def _legacy_tool_data(outcome: TurnOutcome) -> dict[str, Any] | None:
    action = outcome.action
    if action is None:
        return None
    payload = action.public_payload
    if action.type == "clarification":
        return {
            "type": "clarification_request",
            "action_id": action.id,
            "thread_id": outcome.conversation.id,
            "clarifying_question": payload.get("question"),
            "suggested_inputs": payload.get("suggested_inputs") or [],
        }
    return {
        "type": action.type,
        "quiz_id": action.id,
        "thread_id": outcome.conversation.id,
        "quiz_type": action.type,
        "concept": payload.get("target_concept") or "core_concept",
        "question": payload.get("question"),
        "options": [
            str(option.get("text", "")) for option in payload.get("options", [])
        ],
    }


def _legacy_branch(outcome: TurnOutcome) -> str:
    if outcome.action and outcome.action.type == "clarification":
        return "clarify"
    if outcome.action:
        return "understanding_check"
    if suggestions(outcome.result):
        return "followup"
    return str((outcome.result.get("route") or {}).get("name") or "simple")


def _legacy_orchestrator(outcome: TurnOutcome) -> dict[str, Any]:
    branch = _legacy_branch(outcome)
    titles = {
        "simple": "Câu hỏi đơn giản",
        "clarify": "Thiếu thông tin → Hỏi làm rõ",
        "understanding_check": "Cần kiểm tra hiểu",
        "followup": "Có thể đào sâu → Follow-up Suggestions",
        "deep": "Có thể đào sâu",
        "check": "Cần kiểm tra hiểu",
    }
    route = outcome.result.get("route") or {}
    return {
        "branch": branch,
        "title": titles.get(branch, "VLearn Learning Loop"),
        "description": "VLearn đã chọn bước hỗ trợ phù hợp.",
        "next_node": (
            "awaiting_response" if outcome.action else outcome.result.get("status")
        ),
        "confidence": route.get("confidence"),
        "route": route.get("name"),
    }


def _legacy_sources(
    request: Request, citations: list, fallback_page: int, fallback_deck_id: str
) -> list[dict[str, Any]]:
    pages = sorted(
        {
            citation.page_number or fallback_page
            for citation in citations
            if citation.page_number or fallback_page
        }
    )
    output: list[dict[str, Any]] = []
    for page in pages:
        citation = next((item for item in citations if item.page_number == page), None)
        deck_id = (citation.deck_id if citation else None) or fallback_deck_id
        slide = _slides(request).resolve(page, deck_id=deck_id) or {}
        output.append(
            {
                "page": page,
                "title": slide.get("title") or f"Slide {page}",
                "snippet": (citation.snippet if citation else "")[:260],
                "source_location": (
                    citation.source_location if citation else f"trang {page}"
                ),
                "deck_id": deck_id,
            }
        )
    return output


def to_legacy_tutor_response(request: Request, outcome: TurnOutcome) -> dict[str, Any]:
    citations = public_citations(
        outcome.result.get("citations") or [], outcome.page_number, outcome.deck_id
    )
    pages = sorted(
        {
            citation.page_number or outcome.page_number
            for citation in citations
            if citation.page_number or outcome.page_number
        }
    )
    return {
        "status": ("failed" if outcome.result.get("status") == "failed" else "success"),
        "thread_id": outcome.conversation.id,
        "turn_id": outcome.turn.id,
        "answer": outcome.result.get("assistant_message") or "",
        "citations": pages,
        "citation_objects": [item.model_dump() for item in citations],
        "sources": _legacy_sources(request, citations, outcome.page_number, outcome.deck_id),
        "orchestrator": _legacy_orchestrator(outcome),
        "tool_data": _legacy_tool_data(outcome),
        "default_suggestions": suggestions(outcome.result),
        "page": outcome.page_number,
        "deck_id": outcome.deck_id,
        "ai_core_status": outcome.result.get("status"),
        "model_engine": os.environ.get("OPENAI_MODEL", "gpt-5-nano"),
    }


@router.get("/api/health")
async def legacy_health(request: Request):
    service = _service(request)
    return {
        "status": "ok",
        "ai_core_loaded": service.ai_core.available,
        "openai_key_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "slide_count": len(_slides(request).slides),
    }


@router.get("/api/slides")
async def get_slides(request: Request, deck: str | None = None):
    slides = _slides(request).list_slides(deck)
    return {
        "total_pages": len(slides),
        "slides": slides,
        "pdf_decks": [
            {
                "id": "d1",
                "name": "d1-slide-hackathon.pdf (Day 1: AI & LLM Foundation)",
            },
            {
                "id": "d2",
                "name": "d2-slide-hackathon.pdf (Day 2: Xác định bài toán cho AI)",
            },
        ],
    }


@router.get("/api/slides/{page_number}/render")
async def render_slide(page_number: int, request: Request, deck_id: str = "d1"):
    resolved = _slides(request).pdf_path_for_page(page_number, deck_id=deck_id)
    if resolved is None:
        from backend.app.errors import ResourceNotFoundError

        raise ResourceNotFoundError()
    pdf_path, page_index = resolved
    if not pdf_path.exists():
        from backend.app.errors import ResourceNotFoundError

        raise ResourceNotFoundError()
    try:
        import fitz

        with fitz.open(str(pdf_path)) as document:
            if page_index < 0 or page_index >= len(document):
                from backend.app.errors import ResourceNotFoundError

                raise ResourceNotFoundError()
            pixmap = document[page_index].get_pixmap(matrix=fitz.Matrix(2, 2))
            return Response(content=pixmap.tobytes("png"), media_type="image/png")
    except BackendError:
        raise
    except Exception as exc:
        raise AIServiceError("Slide rendering failed.") from exc


async def _run_legacy_ask(payload: LegacyAskRequest, request: Request):
    return await _service(request).legacy_ask(
        owner_id=_owner(request),
        conversation_id=payload.thread_id,
        question=payload.question,
        selected_text=payload.selected_text,
        page_number=payload.page_number,
        deck_id=payload.deck_id,
        chat_history=payload.chat_history,
    )


@router.post("/api/tutor/ask")
async def tutor_ask(payload: LegacyAskRequest, request: Request):
    outcome = await _run_legacy_ask(payload, request)
    return to_legacy_tutor_response(request, outcome)


@router.post("/api/tutor/ask/stream")
async def tutor_ask_stream(payload: LegacyAskRequest, request: Request):
    request_id = request.state.request_id

    def emit(event_type: str, **data: Any) -> str:
        return (
            "data: "
            + json.dumps(
                {"type": event_type, "request_id": request_id, **data},
                ensure_ascii=False,
            )
            + "\n\n"
        )

    async def event_stream():
        yield emit(
            "trace",
            tool="request",
            title="Tiếp nhận yêu cầu",
            status="completed",
            detail="Yêu cầu đã được kiểm tra và tiếp nhận.",
        )
        yield emit(
            "trace",
            tool="learning_loop",
            title="VLearn Learning Loop",
            status="running",
            detail="Đang phân tích ngữ cảnh và chọn bước hỗ trợ.",
        )
        try:
            outcome = await _run_legacy_ask(payload, request)
            yield emit(
                "trace",
                tool="learning_loop",
                title="VLearn Learning Loop",
                status="completed",
                detail="Đã hoàn tất bước xử lý hiện tại.",
            )
            yield emit("result", data=to_legacy_tutor_response(request, outcome))
        except BackendError as exc:
            yield emit(
                "error",
                error={"code": exc.code, "message": exc.public_message},
                message=exc.public_message,
            )
        except Exception:  # noqa: BLE001 - SSE must emit a safe terminal event
            yield emit(
                "error",
                error={
                    "code": "INTERNAL_ERROR",
                    "message": "Không thể hoàn tất luồng xử lý.",
                },
                message="Không thể hoàn tất luồng xử lý.",
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/api/clarification/submit")
async def submit_clarification(payload: LegacyClarificationRequest, request: Request):
    pending = await _service(request).repository.pending_action_for_conversation(
        payload.thread_id, _owner(request)
    )
    if pending is None or pending.type != "clarification":
        raise InvalidActionError()
    digest = hashlib.sha256(payload.answer.encode()).hexdigest()[:24]
    outcome = await _service(request).respond(
        owner_id=_owner(request),
        turn_id=pending.turn_id,
        action_id=pending.id,
        value=payload.answer,
        idempotency_key=f"legacy-clar-{pending.id}-{digest}",
    )
    return to_legacy_tutor_response(request, outcome)


@router.post("/api/quiz/submit")
async def submit_quiz(payload: LegacyQuizRequest, request: Request):
    action = await _service(request).repository.get_action(
        payload.quiz_id, _owner(request)
    )
    if action.type not in {"multiple_choice", "short_answer"}:
        raise InvalidActionError()

    value = payload.user_text_answer.strip()
    if action.type == "multiple_choice" and payload.selected_option is not None:
        options = action.public_payload.get("options") or []
        if payload.selected_option >= len(options):
            raise InvalidActionError()
        value = str(options[payload.selected_option].get("id", ""))
    if not value:
        raise InvalidActionError()

    digest = hashlib.sha256(value.encode()).hexdigest()[:24]
    outcome = await _service(request).respond(
        owner_id=_owner(request),
        turn_id=action.turn_id,
        action_id=action.id,
        value=value,
        idempotency_key=f"legacy-quiz-{action.id}-{digest}",
    )
    is_correct = bool(outcome.check_attempt and outcome.check_attempt.is_correct)
    formatted = to_legacy_tutor_response(request, outcome)
    misconception = None
    if not is_correct:
        misconception = {
            "misconception_point": (
                outcome.check_attempt.misconception_code
                if outcome.check_attempt
                else "concept_confusion"
            ),
            "re_explanation": outcome.result.get("assistant_message")
            or "Câu trả lời chưa khớp với nội dung bài học.",
            "new_example": outcome.result.get("assistant_message")
            or "Hãy xem lại phần giải thích và thử câu kiểm tra tiếp theo.",
            "recheck_question": _legacy_tool_data(outcome),
        }
    return {
        "is_correct": is_correct,
        "feedback": (
            "Đúng rồi. Bạn đã nắm đúng ý chính."
            if is_correct
            else "Chưa chính xác. Tutor đã tạo phần sửa hiểu nhầm bên dưới."
        ),
        "next_step": "followup" if is_correct else "misconception_explanation",
        "misconception": misconception,
        "tutor_response": formatted,
        "default_suggestions": formatted["default_suggestions"],
        "model_engine": formatted["model_engine"],
    }
