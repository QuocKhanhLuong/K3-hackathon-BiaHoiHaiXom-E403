"""Unit tests for misconception detection and repair."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from vlearn_ai.schemas import CheckEvaluation
from vlearn_ai.workflows.detect_misconception import run_detect_misconception
from vlearn_ai.workflows.repair_misconception import run_repair_misconception


@pytest.mark.asyncio
async def test_detect_misconception_correct():
    fake_llm = FakeListChatModel(responses=[""])
    res = await run_detect_misconception(
        question="Key làm gì?",
        expected_answer="So khớp",
        student_answer="đúng",
        context="Key dùng để so khớp.",
        model=fake_llm,
    )
    assert res.is_correct is True


@pytest.mark.asyncio
async def test_detect_misconception_incorrect():
    fake_llm = FakeListChatModel(responses=[""])
    res = await run_detect_misconception(
        question="Key làm gì?",
        expected_answer="So khớp",
        student_answer="Key chứa giá trị tổng hợp",
        context="Key dùng để so khớp.",
        model=fake_llm,
    )
    assert res.is_correct is False
    assert res.misconception_code is not None


@pytest.mark.asyncio
async def test_repair_misconception_plan():
    fake_llm = FakeListChatModel(responses=["Response..."])
    check_eval = CheckEvaluation(
        is_correct=False,
        score=0.0,
        misconception_code="confuses_key_with_value",
        error_explanation="Học viên nhầm Key với Value",
        answer_evidence="Key chứa giá trị tổng hợp",
        recommended_repair_strategy="review_concept_and_example",
    )
    plan, repair_text = await run_repair_misconception(
        check_eval=check_eval,
        context="Key dùng để so khớp.",
        target_concept="Key vs Value",
        model=fake_llm,
    )
    assert len(plan.tools) > 0
    # Verify plan tools are exclusively allowed tools
    for tool in plan.tools:
        assert tool in {"review_concept", "give_example", "give_hint", "motivate"}
    assert repair_text != ""
