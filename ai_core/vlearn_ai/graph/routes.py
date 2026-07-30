"""Conditional routing logic for LangGraph edges."""

from typing import Literal

from vlearn_ai.config import get_settings
from vlearn_ai.graph.state import LearningLoopState


def route_after_input_guard(
    state: LearningLoopState,
) -> Literal["context_guard", "end"]:
    """Route based on input guard result."""
    if state.get("status") == "blocked":
        return "end"
    return "context_guard"


def route_after_router(
    state: LearningLoopState,
) -> Literal["simple", "clarify", "check", "deep"]:
    """Route after router classification."""
    route = state.get("route", "simple")
    if route in ("simple", "clarify", "check", "deep"):
        return route  # type: ignore
    return "simple"


def route_after_ask_clarification(
    state: LearningLoopState,
) -> Literal["grounded_answer", "end"]:
    """Route after ask clarification node."""
    if state.get("status") == "awaiting_clarification" or not state.get(
        "clarification_answer"
    ):
        return "end"
    return "grounded_answer"


def route_after_grounding_guard(
    state: LearningLoopState,
) -> Literal["output_guard", "check_understanding"]:
    """Route after grounding guard."""
    route = state.get("route")
    if route == "simple":
        return "output_guard"
    return "check_understanding"


def route_after_check_eval(
    state: LearningLoopState,
) -> Literal["suggest_followups", "misconception", "output_guard", "end"]:
    """Route after checking evaluation answer."""
    if state.get("status") == "completed":
        return "output_guard"

    check_res = state.get("check_result")
    if not isinstance(check_res, dict) or not check_res:
        return "end"

    is_correct = check_res.get("is_correct", False)

    if is_correct:
        return "suggest_followups"

    retry = state.get("retry_count", 0)
    max_retry = get_settings().AI_MAX_RETRY_COUNT
    if retry >= max_retry:
        return "output_guard"

    return "misconception"
