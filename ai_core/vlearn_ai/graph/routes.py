"""LangGraph routing functions for conditional workflow edges."""

from typing import Literal

from vlearn_ai.config import get_settings
from vlearn_ai.graph.state import LearningLoopState


def route_after_input_guard(
    state: LearningLoopState,
) -> Literal["context_guard", "output_guard"]:
    """Route after input guard."""
    if state.get("status") == "blocked":
        return "output_guard"
    return "context_guard"


def route_after_context_guard(
    state: LearningLoopState,
) -> Literal["router", "output_guard"]:
    """Stop before model invocation when course context contains injection."""
    if state.get("status") == "blocked":
        return "output_guard"
    return "router"


def route_after_router(
    state: LearningLoopState,
) -> Literal[
    "generate_clarification",
    "grounded_answer",
]:
    """Route after router classification."""
    route = state.get("route")
    if route == "clarify":
        return "generate_clarification"
    return "grounded_answer"


def route_after_await_clarification(
    state: LearningLoopState,
) -> Literal["guard_clarification_input", "output_guard"]:
    """Route after await clarification node."""
    if state.get("status") == "awaiting_clarification":
        return "output_guard"
    return "guard_clarification_input"


def route_after_guard_clarification_input(
    state: LearningLoopState,
) -> Literal["grounded_answer", "output_guard"]:
    """Route after clarification input prompt injection guard."""
    if state.get("status") == "blocked":
        return "output_guard"
    return "grounded_answer"


def route_after_grounding_guard(
    state: LearningLoopState,
) -> Literal[
    "output_guard", "suggest_followups", "generate_check", "grounding_failure"
]:
    """Route after grounding guard."""
    valid = state.get("grounding_valid")
    if valid is False:
        return "grounding_failure"

    route = state.get("route")
    if route == "simple" or route == "clarify":
        return "suggest_followups"
    if route == "deep":
        return "suggest_followups"
    return "generate_check"


def route_after_await_check(
    state: LearningLoopState,
) -> Literal["guard_check_input", "output_guard"]:
    """Route after await check node."""
    if state.get("status") == "awaiting_check":
        return "output_guard"
    return "guard_check_input"


def route_after_guard_check_input(
    state: LearningLoopState,
) -> Literal["evaluate_check", "output_guard"]:
    """Route after check input prompt injection guard."""
    if state.get("status") == "blocked":
        return "output_guard"
    return "evaluate_check"


def route_after_check_eval(
    state: LearningLoopState,
) -> Literal["suggest_followups", "misconception", "safe_end"]:
    """Route after student check answer evaluation."""
    res = state.get("check_result") or {}
    if res.get("is_correct") is True:
        return "suggest_followups"

    retry = state.get("retry_count", 0)
    settings = get_settings()
    if retry >= settings.AI_MAX_RETRY_COUNT:
        return "safe_end"

    return "misconception"


def route_after_misconception(
    state: LearningLoopState,
) -> Literal["generate_check"]:
    """Route after misconception repair back to generate_check."""
    return "generate_check"
