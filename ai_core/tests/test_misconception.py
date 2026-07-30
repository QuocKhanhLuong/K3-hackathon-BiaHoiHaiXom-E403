"""Unit tests for misconception detection and repair workflows."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.schemas import CheckEvaluation
from vlearn_ai.workflows.detect_misconception import run_detect_misconception
from vlearn_ai.workflows.repair_misconception import run_repair_misconception


@pytest.mark.asyncio
async def test_detect_misconception_correct():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=False)
    res = await run_detect_misconception(
        question="Key là gì?",
        expected_answer="So khớp với Query",
        student_answer="So khớp với Query",
        context="Key dùng để so khớp với Query.",
        model=fake_llm,
    )
    assert res.is_correct is True
    assert res.score == 1.0


@pytest.mark.asyncio
async def test_detect_misconception_incorrect():
    fake_llm = DeterministicFakeChatModel(misconception_to_return=True)
    res = await run_detect_misconception(
        question="Key là gì?",
        expected_answer="So khớp với Query",
        student_answer="Key là chứa nội dung bài học",
        context="Key dùng để so khớp với Query.",
        model=fake_llm,
    )
    assert res.is_correct is False
    assert res.misconception_code != ""


@pytest.mark.asyncio
async def test_repair_misconception_plan_retry_zero_no_motivate():
    fake_llm = DeterministicFakeChatModel()
    check_eval = CheckEvaluation(
        is_correct=False,
        score=0.0,
        misconception_code="confuses_two_concepts",
        error_explanation="Học viên nhầm lẫn.",
        answer_evidence="Bằng chứng",
        recommended_repair_strategy="review_concept_and_example",
    )
    plan, _text, executed_tools = await run_repair_misconception(
        check_eval=check_eval,
        context="Bối cảnh bài học...",
        target_concept="Key",
        retry_count=0,
        model=fake_llm,
    )
    assert "motivate" not in plan.planned_tools
    assert "motivate" not in executed_tools


@pytest.mark.asyncio
async def test_repair_misconception_plan_retry_positive_allows_motivate():
    fake_llm = DeterministicFakeChatModel()
    check_eval = CheckEvaluation(
        is_correct=False,
        score=0.0,
        misconception_code="confuses_two_concepts",
        error_explanation="Học viên nhầm lẫn.",
        answer_evidence="Bằng chứng",
        recommended_repair_strategy="review_concept_and_example",
    )
    _plan, _text, executed_tools = await run_repair_misconception(
        check_eval=check_eval,
        context="Bối cảnh bài học...",
        target_concept="Key",
        retry_count=1,
        model=fake_llm,
    )
    assert len(executed_tools) >= 1
