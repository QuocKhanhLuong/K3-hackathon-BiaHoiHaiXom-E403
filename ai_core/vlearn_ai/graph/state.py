"""LangGraph LearningLoopState TypedDict definition."""

from typing import Any, Literal, TypedDict


class LearningLoopState(TypedDict, total=False):
    """LangGraph state representation across learning loop turns."""

    thread_id: str
    user_query: str
    selected_context: str
    conversation_history: list[dict[str, Any]]

    # Guardrail states
    context_truncated: bool
    context_injection_detected: bool
    grounding_valid: bool | None
    grounding_error: str | None

    # Router classification
    route: Literal["simple", "clarify", "check", "deep"] | None
    route_confidence: float
    route_reason: str

    # Workflow outputs & interrupt payload states
    clarification_question: str | None
    clarification_answer: str | None

    grounded_answer: str | None
    citations: list[dict[str, Any]]

    check_question: dict[str, Any] | None
    student_check_answer: str | None
    check_result: dict[str, Any] | None
    last_check_result: dict[str, Any] | None

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
