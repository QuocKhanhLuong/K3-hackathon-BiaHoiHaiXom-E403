"""Conditional routing logic for LangGraph edges."""

from typing import Literal

from vlearn_ai.config import get_settings
from vlearn_ai.graph.state import LearningLoopState


def route_after_input_guard(
    state: LearningLoopState,
) -> Literal["context_guard", "output_guard"]:
    """Route based on input guard result."""
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
) -> Literal["simple", "generate_clarification", "check", "deep"]:
    """Route after router classification."""
    route = state.get("route", "simple")
    if route == "clarify":
        return "generate_clarification"
    if route in ("simple", "check", "deep"):
        return route  # type: ignore
    return "simple"


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
    """Route after checking clarification input guard."""
    if state.get("status") == "blocked":
        return "output_guard"
    return "grounded_answer"


def route_after_grounding_guard(
    state: LearningLoopState,
) -> Literal["output_guard", "suggest_followups", "generate_check"]:
    """Route after grounding guard."""
    valid = state.get("grounding_valid")
    if valid is False:
        return "output_guard"

    route = state.get("route")
    if route == "simple":
        return "output_guard"
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
    """Route after checking check answer input guard."""
    if state.get("status") == "blocked":
        return "output_guard"
    return "evaluate_check"


def route_after_check_eval(
    state: LearningLoopState,
) -> Literal["suggest_followups", "misconception", "safe_end"]:
    """Route after checking evaluation answer."""
    check_res = state.get("check_result") or {}
    is_correct = check_res.get("is_correct", False)

    if is_correct:
        return "suggest_followups"

    retry = state.get("retry_count", 0)
    max_retry = get_settings().AI_MAX_RETRY_COUNT
    if retry >= max_retry:
        return "safe_end"

    return "misconception"
