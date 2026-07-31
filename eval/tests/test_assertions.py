"""Unit tests for hard deterministic assertion engine."""

from eval.assertions import evaluate_turn_assertions
from eval.schemas import TurnExecutionResult, TurnExpectations


def test_assertions_route_and_status():
    turn_res = TurnExecutionResult(
        scenario_id="SCEN-1",
        turn_index=1,
        input_type="user_turn",
        input_text="Test",
        route="simple",
        status="completed",
    )
    expected = TurnExpectations(routes=["simple"], statuses=["completed"])
    assertions = evaluate_turn_assertions(turn_res, expected)
    assert all(a.passed for a in assertions)


def test_assertions_required_tools_missing_fails():
    turn_res = TurnExecutionResult(
        scenario_id="SCEN-1",
        turn_index=1,
        input_type="user_turn",
        input_text="Test",
        status="completed",
        tool_sequence=["input_guard", "router"],
    )
    expected = TurnExpectations(required_tools=["input_guard", "review_concept"])
    assertions = evaluate_turn_assertions(turn_res, expected)
    req_assert = next(a for a in assertions if a.name == "required_tools")
    assert req_assert.passed is False


def test_assertions_forbidden_tools_executed_fails():
    turn_res = TurnExecutionResult(
        scenario_id="SCEN-1",
        turn_index=1,
        input_type="user_turn",
        input_text="Test",
        status="completed",
        tool_sequence=["input_guard", "failure_node"],
    )
    expected = TurnExpectations(forbidden_tools=["failure_node"])
    assertions = evaluate_turn_assertions(turn_res, expected)
    forbid_assert = next(a for a in assertions if a.name == "forbidden_tools")
    assert forbid_assert.passed is False


def test_assertions_tool_order_out_of_sequence_fails():
    turn_res = TurnExecutionResult(
        scenario_id="SCEN-1",
        turn_index=1,
        input_type="user_turn",
        input_text="Test",
        status="completed",
        tool_sequence=["review_concept", "router"],
    )
    expected = TurnExpectations(expected_tool_order=[["router", "review_concept"]])
    assertions = evaluate_turn_assertions(turn_res, expected)
    order_assert = next(a for a in assertions if a.name == "expected_tool_order")
    assert order_assert.passed is False


def test_assertions_stale_citations_detected():
    prev_turn = TurnExecutionResult(
        scenario_id="SCEN-1",
        turn_index=1,
        input_type="user_turn",
        input_text="Turn 1",
        status="completed",
        citation_ids=["cit_1", "cit_2"],
    )
    curr_turn = TurnExecutionResult(
        scenario_id="SCEN-1",
        turn_index=2,
        input_type="user_turn",
        input_text="Turn 2",
        status="completed",
        citation_ids=["cit_1", "cit_2"],
    )
    expected = TurnExpectations(no_stale_citations=True)
    assertions = evaluate_turn_assertions(
        curr_turn, expected, previous_turn_res=prev_turn
    )
    stale_assert = next(a for a in assertions if a.name == "no_stale_citations")
    assert stale_assert.passed is False
