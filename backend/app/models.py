"""Internal application records and service outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ConversationRecord:
    id: str
    owner_id: str
    course_id: str
    status: str = "active"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    turn_ids: list[str] = field(default_factory=list)
    message_ids: list[str] = field(default_factory=list)


@dataclass
class TurnRecord:
    id: str
    conversation_id: str
    ai_thread_id: str
    user_query: str
    page_number: int
    status: str = "processing"
    route: str | None = None
    raw_result: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class MessageRecord:
    id: str
    conversation_id: str
    turn_id: str
    role: str
    content: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class PendingActionRecord:
    id: str
    conversation_id: str
    turn_id: str
    type: str
    public_payload: dict[str, Any]
    private_payload: dict[str, Any]
    status: str = "pending"
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None


@dataclass
class CheckAttemptRecord:
    id: str
    action_id: str
    turn_id: str
    answer: str
    is_correct: bool
    score: float | None = None
    misconception_code: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class CoreInvocation:
    result: dict[str, Any]
    state: dict[str, Any]


@dataclass
class TurnOutcome:
    conversation: ConversationRecord
    turn: TurnRecord
    result: dict[str, Any]
    action: PendingActionRecord | None
    page_number: int
    check_attempt: CheckAttemptRecord | None = None
    previous_action: PendingActionRecord | None = None
