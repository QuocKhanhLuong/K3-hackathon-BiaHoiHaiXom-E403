"""Unit tests for offline evaluation runner multi-turn execution."""

import pytest

from eval.runner import ScenarioRunner
from eval.schemas import (
    ScenarioDefinition,
    ScenarioSetup,
    ScenarioTurn,
    TurnExpectations,
)


@pytest.mark.asyncio
async def test_offline_runner_single_turn():
    runner = ScenarioRunner(mode="offline")
    scen = ScenarioDefinition(
        id="OFFLINE-001",
        name="Offline Test",
        description="Single turn offline test",
        tags=["unit_test"],
        mode="offline",
        setup=ScenarioSetup(selected_text="Key dùng để so khớp với Query."),
        turns=[
            ScenarioTurn(
                type="user_turn",
                input="Key là gì?",
                expected=TurnExpectations(
                    routes=["simple"],
                    statuses=["completed"],
                    assistant_message_required=True,
                ),
            )
        ],
    )
    result = await runner.run_scenario(scen)
    assert result.passed is True
    assert len(result.turn_results) == 1
    assert result.turn_results[0].status == "completed"


@pytest.mark.asyncio
async def test_offline_runner_multi_turn_start_and_resume():
    runner = ScenarioRunner(mode="offline")
    scen = ScenarioDefinition(
        id="OFFLINE-002",
        name="Multi Turn Resume Test",
        description="Multi turn test exercising start_turn then resume_turn",
        tags=["multi_turn", "route_check"],
        mode="offline",
        setup=ScenarioSetup(selected_text="Key dùng để so khớp với Query."),
        turns=[
            ScenarioTurn(
                type="user_turn",
                input="So sánh Key và Value.",
                expected=TurnExpectations(
                    routes=["check"],
                    statuses=["awaiting_check"],
                ),
            ),
            ScenarioTurn(
                type="action_response",
                input="opt_a",
                expected=TurnExpectations(
                    statuses=["completed"],
                    assistant_message_required=True,
                ),
            ),
        ],
    )
    result = await runner.run_scenario(scen)
    assert result.passed is True
    assert len(result.turn_results) == 2
    assert result.turn_results[0].input_type == "user_turn"
    assert result.turn_results[0].status == "awaiting_check"
    assert result.turn_results[1].input_type == "action_response"
    assert result.turn_results[1].status == "completed"
