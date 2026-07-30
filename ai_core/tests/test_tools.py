"""Unit tests for all 6 pedagogical tools and MCQ evaluation."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.schemas import CheckOption, MicroCheck
from vlearn_ai.tools.give_direct_answer import execute_give_direct_answer
from vlearn_ai.tools.give_example import execute_give_example
from vlearn_ai.tools.give_hint import execute_give_hint
from vlearn_ai.tools.motivate import execute_motivate
from vlearn_ai.tools.review_concept import execute_review_concept
from vlearn_ai.tools.validate_understanding import (
    evaluate_mcq_student_answer,
    execute_validate_understanding,
)


@pytest.mark.asyncio
async def test_tool_review_concept():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_review_concept(
        query="Key là gì?", context="Key dùng để so khớp.", model=fake_llm
    )
    assert res.answer != ""
    assert len(res.citations) > 0


@pytest.mark.asyncio
async def test_tool_give_direct_answer():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_give_direct_answer(
        query="Key là gì?", context="Key dùng để so khớp.", model=fake_llm
    )
    assert res.answer != ""


@pytest.mark.asyncio
async def test_tool_give_example():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_give_example(
        concept="Key", context="Key dùng để so khớp.", model=fake_llm
    )
    assert res.example != ""


@pytest.mark.asyncio
async def test_tool_motivate():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_motivate(
        difficulty="Học viên gặp khó khăn khi phân biệt Key và Value", model=fake_llm
    )
    assert res.message != ""


@pytest.mark.asyncio
async def test_tool_give_hint():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_give_hint(
        concept="Key", context="Key dùng...", hint_level=1, model=fake_llm
    )
    assert res.hint != ""


@pytest.mark.asyncio
async def test_tool_validate_understanding_generate():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_validate_understanding(
        mode="generate_check",
        context="Key dùng để so khớp.",
        grounded_answer="Key giải thích",
        model=fake_llm,
    )
    assert isinstance(res, MicroCheck)
    assert res.question != ""


def test_mcq_evaluation_no_false_positive_sai():
    options = [
        CheckOption(option_id="opt_a", text="So khớp với Query"),
        CheckOption(option_id="opt_b", text="Lưu trữ kết quả"),
    ]
    # Word "sai" should NOT be matched as correct (previously contains "a" substring bug)
    is_correct = evaluate_mcq_student_answer(
        student_answer="sai",
        correct_option_id="opt_a",
        options=options,
        expected_answer="So khớp với Query",
    )
    assert is_correct is False


def test_mcq_evaluation_option_letter_matching():
    options = [
        CheckOption(option_id="opt_a", text="So khớp với Query"),
        CheckOption(option_id="opt_b", text="Lưu trữ kết quả"),
    ]
    assert (
        evaluate_mcq_student_answer("A", "opt_a", options, "So khớp với Query") is True
    )
    assert (
        evaluate_mcq_student_answer("lựa chọn A", "opt_a", options, "So khớp với Query")
        is True
    )
    assert (
        evaluate_mcq_student_answer("B", "opt_a", options, "So khớp với Query") is False
    )
