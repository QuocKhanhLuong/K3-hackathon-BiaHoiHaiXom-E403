"""Regression tests for terminal insufficient-context routing."""

import pytest
from vlearn_ai.graph.routes import route_after_grounding_guard


@pytest.mark.parametrize("route", ["simple", "deep", "check", "clarify"])
def test_insufficient_context_bypasses_route_specific_actions(route: str):
    state = {
        "route": route,
        "answerability": "insufficient_context",
        "grounding_valid": True,
        "grounding_retry_count": 0,
    }
    assert route_after_grounding_guard(state) == "suggest_followups"
