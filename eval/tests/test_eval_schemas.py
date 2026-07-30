"""Unit tests for evaluation Pydantic schemas."""

import pytest
from pydantic import ValidationError

from eval.schemas import (
    ScenarioDefinition,
    ScenarioTurn,
    TurnExpectations,
)


def test_turn_expectations_valid():
    exp = TurnExpectations(
        routes=["simple"],
        statuses=["completed"],
        required_tools=["input_guard", "router"],
        forbidden_tools=["ask_clarification"],
        min_citations=1,
    )
    assert exp.routes == ["simple"]
    assert exp.min_citations == 1


def test_turn_expectations_extra_field_rejected():
    with pytest.raises(ValidationError):
        TurnExpectations(invalid_field="test")  # type: ignore


def test_scenario_definition_valid():
    scen = ScenarioDefinition(
        id="TEST-001",
        name="Test Scenario",
        description="A test scenario",
        tags=["unit_test"],
        turns=[
            ScenarioTurn(
                type="user_turn",
                input="Hello",
                expected=TurnExpectations(routes=["simple"]),
            )
        ],
    )
    assert scen.id == "TEST-001"
    assert len(scen.turns) == 1


def test_scenario_definition_empty_id_rejected():
    with pytest.raises(ValidationError):
        ScenarioDefinition(
            id="   ",
            name="Test",
            description="Test",
            turns=[],
        )
