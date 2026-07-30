"""Typed state definition for LangGraph learning loop."""

from typing import Any, Literal

from typing_extensions import TypedDict


class LearningLoopState(TypedDict, total=False):
    """Typed state passed across LangGraph nodes."""

    thread_id: str
    user_query: str
    selected_context: str
    conversation_history: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    route: str | None
    route_confidence: float
    route_reason: str
    clarification_question: str | None
    clarification_answer: str | None
    grounded_answer: str | None
    check_question: dict[str, Any] | None
    student_check_answer: str | None
    check_result: dict[str, Any] | None
    misconception: dict[str, Any] | None
    repair_plan: dict[str, Any] | None
    retry_count: int
    followups: list[dict[str, Any]]
    current_tool: str | None
    tool_trace: list[dict[str, Any]]
    status: Literal[
        "running",
        "awaiting_clarification",
        "awaiting_check",
        "completed",
        "blocked",
        "failed",
    ]
    blocked_reason: str | None
    final_output: dict[str, Any] | None
