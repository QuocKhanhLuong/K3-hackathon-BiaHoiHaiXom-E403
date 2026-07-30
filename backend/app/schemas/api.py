"""Strict request and public response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationCreateRequest(StrictAPIModel):
    course_id: str = Field(default="default", min_length=1, max_length=100)


class TurnCreateRequest(StrictAPIModel):
    question: str = Field(..., min_length=1, max_length=4000)
    selected_text: str = Field(default="", max_length=12000)
    page_number: int = Field(default=1, ge=1, le=9999)
    deck_id: str = Field(default="d1", min_length=1, max_length=100)
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list, max_length=50
    )
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)


class ActionRespondRequest(StrictAPIModel):
    action_id: str = Field(..., min_length=8, max_length=100)
    value: str = Field(..., min_length=1, max_length=4000)
    idempotency_key: str = Field(..., min_length=8, max_length=200)


class PublicOption(StrictAPIModel):
    id: str
    text: str


class PublicAction(StrictAPIModel):
    type: Literal["clarification", "multiple_choice", "short_answer"]
    action_id: str
    question: str
    options: list[PublicOption] = Field(default_factory=list)
    suggested_inputs: list[str] = Field(default_factory=list)
    target_concept: str | None = None


class PublicMessage(StrictAPIModel):
    role: Literal["assistant"]
    content: str


class PublicRoute(StrictAPIModel):
    name: str
    confidence: float | None = None


class PublicCitation(StrictAPIModel):
    citation_id: str
    snippet: str
    source_location: str | None = None
    page_number: int | None = None
    deck_id: str | None = None


class TurnResponse(StrictAPIModel):
    request_id: str
    conversation_id: str
    turn_id: str
    status: Literal["processing", "awaiting_response", "completed", "blocked", "failed"]
    message: PublicMessage
    route: PublicRoute | None = None
    action: PublicAction | None = None
    citations: list[PublicCitation] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ConversationResponse(StrictAPIModel):
    conversation_id: str
    status: str
    course_id: str


class ConversationSnapshotResponse(ConversationResponse):
    messages: list[dict[str, Any]]
    turns: list[dict[str, Any]]
    pending_action: PublicAction | None = None


class LegacyAskRequest(StrictAPIModel):
    question: str = Field(..., min_length=1, max_length=4000)
    selected_text: str = Field(default="", max_length=12000)
    page_number: int = Field(default=1, ge=1, le=9999)
    deck_id: str = Field(default="d1", min_length=1, max_length=100)
    chat_history: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    thread_id: str | None = Field(default=None, max_length=100)


class LegacyClarificationRequest(StrictAPIModel):
    thread_id: str = Field(..., min_length=8, max_length=100)
    answer: str = Field(..., min_length=1, max_length=4000)


class LegacyQuizRequest(StrictAPIModel):
    quiz_id: str = Field(..., min_length=8, max_length=100)
    thread_id: str | None = Field(default=None, max_length=100)
    quiz_type: Literal["multiple_choice", "short_answer"] = "multiple_choice"
    selected_option: int | None = Field(default=None, ge=0, le=10)
    user_text_answer: str = Field(default="", max_length=4000)
    question_text: str = Field(default="", max_length=4000)
    page_number: int = Field(default=1, ge=1, le=9999)
