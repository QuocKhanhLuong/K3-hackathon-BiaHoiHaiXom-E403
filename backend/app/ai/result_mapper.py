"""Map AI Core state into stable public actions and HTTP response models."""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.app.models import PendingActionRecord, TurnOutcome
from backend.app.schemas.api import (
    PublicAction,
    PublicCitation,
    PublicMessage,
    PublicOption,
    PublicRoute,
    TurnResponse,
)

CLARIFICATION_SUGGESTIONS = [
    "Mình muốn hiểu định nghĩa và ý chính.",
    "Mình muốn xem một ví dụ cụ thể.",
    "Mình muốn biết cách áp dụng vào bài học.",
]


def action_payloads(
    result: dict[str, Any], state: dict[str, Any]
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    """Split an interrupted AI state into public and server-private payloads."""
    status = result.get("status")
    ui_payload = result.get("ui_payload") or {}

    if status == "awaiting_clarification":
        question = (
            ui_payload.get("question")
            or state.get("clarification_question")
            or result.get("assistant_message")
            or "Bạn có thể làm rõ câu hỏi không?"
        )
        public = {
            "question": str(question),
            "suggested_inputs": list(CLARIFICATION_SUGGESTIONS),
            "options": [],
        }
        return "clarification", public, {"question": str(question)}

    if status != "awaiting_check":
        return None

    full_check = state.get("check_question") or {}
    question = full_check.get("question") or ui_payload.get("question") or ""
    question_type = full_check.get("question_type") or ui_payload.get(
        "type", "multiple_choice"
    )
    raw_options = full_check.get("options") or ui_payload.get("options") or []
    options = [
        {
            "id": str(option.get("option_id", f"opt_{index}")),
            "text": str(option.get("text", "")),
        }
        for index, option in enumerate(raw_options)
        if isinstance(option, dict)
    ]
    action_type = (
        "short_answer" if question_type == "short_answer" else "multiple_choice"
    )
    public = {
        "question": str(question),
        "options": options,
        "suggested_inputs": [],
        "target_concept": full_check.get("target_concept"),
    }
    private = {
        "correct_option_id": full_check.get("correct_option_id"),
        "expected_answer": full_check.get("expected_answer"),
        "explanation": full_check.get("explanation"),
        "evidence": full_check.get("evidence") or [],
        "raw_options": raw_options,
    }
    return action_type, public, private


def public_action(action: PendingActionRecord | None) -> PublicAction | None:
    if action is None:
        return None
    payload = action.public_payload
    return PublicAction(
        type=action.type,  # type: ignore[arg-type]
        action_id=action.id,
        question=str(payload.get("question", "")),
        options=[
            PublicOption(id=str(option["id"]), text=str(option["text"]))
            for option in payload.get("options", [])
        ],
        suggested_inputs=[str(item) for item in payload.get("suggested_inputs", [])],
        target_concept=payload.get("target_concept"),
    )


def _page_from_citation(citation: dict[str, Any]) -> int | None:
    haystack = " ".join(
        str(citation.get(key, ""))
        for key in ("citation_id", "source_id", "source_location", "snippet")
    )
    match = re.search(
        r"(?:page[=\s]|page_in_deck[=\s]|p|-p)(\d{1,4})", haystack, re.IGNORECASE
    )
    if match:
        return int(match.group(1))
    match = re.search(r"(?:trang|page|p)\D*(\d{1,4})", haystack, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _deck_from_citation(citation: dict[str, Any]) -> str | None:
    """Extract the deck prefix from canonical source IDs such as d2-p1."""
    source_id = str(citation.get("citation_id") or citation.get("source_id") or "")
    match = re.match(r"([A-Za-z0-9_-]+)-p\d+$", source_id)
    return match.group(1) if match else None


def public_citations(
    citations: list[dict[str, Any]],
    fallback_page: int | None = None,
    fallback_deck_id: str | None = None,
) -> list[PublicCitation]:
    output: list[PublicCitation] = []
    for index, item in enumerate(citations):
        if not isinstance(item, dict):
            continue
        output.append(
            PublicCitation(
                citation_id=str(item.get("citation_id") or f"citation_{index + 1}"),
                snippet=str(item.get("snippet") or ""),
                source_location=(
                    str(item["source_location"])
                    if item.get("source_location")
                    else None
                ),
                page_number=_page_from_citation(item) or fallback_page,
                deck_id=(
                    str(item.get("deck_id"))
                    if item.get("deck_id")
                    else _deck_from_citation(item) or fallback_deck_id
                ),
            )
        )
    return output


def public_status(result: dict[str, Any], action: PendingActionRecord | None) -> str:
    if action is not None:
        return "awaiting_response"
    status = str(result.get("status") or "completed")
    return status if status in {"completed", "blocked", "failed"} else "processing"


def suggestions(result: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for item in result.get("followups") or []:
        if isinstance(item, dict):
            value = item.get("question") or item.get("label")
        else:
            value = item
        if value:
            output.append(str(value))
    return output[:3]


def to_turn_response(
    outcome: TurnOutcome, request_id: str | None = None
) -> TurnResponse:
    result = outcome.result
    message = result.get("assistant_message") or ""
    if result.get("status") == "blocked" and not message:
        message = "Yêu cầu này không thể được xử lý an toàn."
    route_data = result.get("route") or {}
    route = (
        PublicRoute(
            name=str(route_data.get("name")),
            confidence=route_data.get("confidence"),
        )
        if route_data.get("name")
        else None
    )
    return TurnResponse(
        request_id=request_id or f"req_{uuid.uuid4().hex}",
        conversation_id=outcome.conversation.id,
        turn_id=outcome.turn.id,
        status=public_status(result, outcome.action),  # type: ignore[arg-type]
        message=PublicMessage(role="assistant", content=str(message)),
        route=route,
        action=public_action(outcome.action),
        citations=public_citations(result.get("citations") or [], outcome.page_number, outcome.deck_id),
        suggestions=suggestions(result),
    )
