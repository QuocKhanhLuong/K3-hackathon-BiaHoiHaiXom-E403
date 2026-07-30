"""Unit tests for offline evaluation runner multi-turn execution."""

import pytest

from eval.runner import ScenarioRunner
from eval.schemas import (
    OfflineFixture,
    ScenarioDefinition,
    ScenarioSetup,
    ScenarioTurn,
    ScriptedOutput,
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
        offline_fixture=OfflineFixture(
            model_script=[
                ScriptedOutput(
                    schema="RouteOutput",
                    output={"route": "simple", "confidence": 0.98, "reason": "Simple"},
                ),
                ScriptedOutput(
                    schema="GroundedAnswer",
                    output={
                        "answer": "Key dùng để so khớp với Query.",
                        "claims": [{"claim": "Key dùng để so khớp với Query.", "citation_ids": ["d1-p1"]}],
                        "citations": [{"citation_id": "d1-p1", "snippet": "Key dùng để so khớp với Query."}],
                    },
                ),
            ]
        ),
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
        offline_fixture=OfflineFixture(
            model_script=[
                ScriptedOutput(
                    schema="RouteOutput",
                    output={"route": "check", "confidence": 0.95, "reason": "Check"},
                ),
                ScriptedOutput(
                    schema="GroundedAnswer",
                    output={
                        "answer": "Key dùng để so khớp với Query.",
                        "claims": [{"claim": "Key dùng để so khớp với Query.", "citation_ids": ["d1-p1"]}],
                        "citations": [{"citation_id": "d1-p1", "snippet": "Key dùng để so khớp với Query."}],
                    },
                ),
                ScriptedOutput(
                    schema="GiveExampleOutput",
                    output={"example": "Ex", "relevance_explanation": "Rel"},
                ),
                ScriptedOutput(
                    schema="MicroCheck",
                    output={
                        "question": "Q?",
                        "question_type": "multiple_choice",
                        "target_concept": "Key",
                        "expected_answer": "Key",
                        "correct_option_id": "opt_a",
                        "options": [
                            {"option_id": "opt_a", "text": "A"},
                            {"option_id": "opt_b", "text": "B"},
                            {"option_id": "opt_c", "text": "C"},
                        ],
                        "explanation": "Exp",
                        "evidence": ["Key"],
                    },
                ),
                ScriptedOutput(
                    schema="CheckEvaluation",
                    output={
                        "is_correct": True,
                        "score": 1.0,
                        "misconception_code": "none",
                        "error_explanation": "Correct",
                        "answer_evidence": "opt_a",
                        "recommended_repair_strategy": "none",
                    },
                ),
                ScriptedOutput(
                    schema="FollowUpSuggestions",
                    output={"followups": [{"label": "L", "question": "Q?"}]},
                ),
            ]
        ),
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
    print("\nALL TRACES:", result.turn_results[0].tool_traces)
    assert result.passed is True
    assert len(result.turn_results) == 2
    assert result.turn_results[0].input_type == "user_turn"
    assert result.turn_results[0].status == "awaiting_check"
    assert result.turn_results[1].input_type == "action_response"
    assert result.turn_results[1].status == "completed"
