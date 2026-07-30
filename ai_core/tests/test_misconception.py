"""Unit tests for misconception detection and repair planning."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.guardrails.plan_guard import validate_plan_tools
from vlearn_ai.schemas import AIStructuredOutputError
from vlearn_ai.workflows.detect_misconception import run_detect_misconception
from vlearn_ai.workflows.repair_misconception import run_repair_misconception


@pytest.mark.asyncio
async def test_detect_misconception_correct():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=False)
    res = await run_detect_misconception(
        question="Key dùng để làm gì?",
        expected_answer="So khớp với Query",
        student_answer="So khớp với Query",
        context="Key dùng để so khớp với Query.",
        correct_option_id="opt_a",
        options=[],
        model=fake_llm,
    )
    assert res.is_correct is True
    assert res.score == 1.0


@pytest.mark.asyncio
async def test_detect_misconception_incorrect():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=True)
    res = await run_detect_misconception(
        question="Key dùng để làm gì?",
        expected_answer="So khớp với Query",
        student_answer="Lưu dữ liệu",
        context="Key dùng để so khớp với Query.",
        correct_option_id="opt_a",
        options=[],
        model=fake_llm,
    )
    assert res.is_correct is False
    assert res.score == 0.0


@pytest.mark.asyncio
async def test_repair_misconception_plan_retry_zero_no_motivate():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=True)
    eval_res = await run_detect_misconception(
        question="Key dùng để làm gì?",
        expected_answer="So khớp với Query",
        student_answer="Lưu dữ liệu",
        context="Key dùng để so khớp với Query.",
        correct_option_id="opt_a",
        options=[],
        model=fake_llm,
    )

    plan, _text, tools = await run_repair_misconception(
        check_eval=eval_res,
        context="Key dùng để so khớp với Query.",
        target_concept="Transformer Key",
        retry_count=0,
        model=fake_llm,
    )
    assert "motivate" not in plan.planned_tools
    assert len(tools) > 0


def test_validate_plan_tools_rejects_unsupported_tools():
    # validate_understanding is not allowed in RepairPlan
    with pytest.raises(AIStructuredOutputError):
        validate_plan_tools(["review_concept", "validate_understanding"], retry_count=1)

    # give_direct_answer is not allowed in RepairPlan
    with pytest.raises(AIStructuredOutputError):
        validate_plan_tools(["give_direct_answer", "give_example"], retry_count=1)

    # motivate forbidden on retry_count == 0
    with pytest.raises(AIStructuredOutputError):
        validate_plan_tools(["motivate", "review_concept"], retry_count=0)
