"""Unit tests for individual pedagogical tools and MicroCheck validators."""

import pytest
from fake_model import DeterministicFakeChatModel
from pydantic import ValidationError
from vlearn_ai.schemas import CheckOption, GroundedAnswer, MicroCheck
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
    res = await execute_review_concept("Transformer Key", "Key dùng để...", fake_llm)
    assert isinstance(res, GroundedAnswer)
    assert "Key dùng để" in res.answer


@pytest.mark.asyncio
async def test_tool_give_direct_answer():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_give_direct_answer("Key là gì?", "Key dùng để...", fake_llm)
    assert isinstance(res, GroundedAnswer)
    assert len(res.citations) > 0


@pytest.mark.asyncio
async def test_tool_give_example():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_give_example("Transformer Key", "Key dùng để...", fake_llm)
    assert res.example != ""


@pytest.mark.asyncio
async def test_tool_motivate():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_motivate("Khó hiểu quá", fake_llm)
    assert res.message != ""


@pytest.mark.asyncio
async def test_tool_give_hint():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_give_hint("Transformer Key", "Key dùng để...", 1, fake_llm)
    assert res.hint != ""


@pytest.mark.asyncio
async def test_tool_validate_understanding_generate():
    fake_llm = DeterministicFakeChatModel()
    res = await execute_validate_understanding(
        mode="generate_check",
        context="Key dùng để...",
        grounded_answer="Key dùng để so khớp với Query.",
        model=fake_llm,
    )
    assert isinstance(res, MicroCheck)
    assert res.question != ""


def test_mcq_evaluation_no_false_positive_sai():
    opts = [
        CheckOption(option_id="opt_a", text="So khớp với Query."),
        CheckOption(option_id="opt_b", text="Lưu dữ liệu."),
        CheckOption(option_id="opt_c", text="Tính điểm chú ý."),
    ]
    # "sai rồi" should not match option "opt_a"
    assert (
        evaluate_mcq_student_answer(
            student_answer="sai rồi",
            correct_option_id="opt_a",
            options=opts,
            expected_answer="So khớp với Query.",
        )
        is False
    )


def test_mcq_evaluation_option_letter_matching():
    opts = [
        CheckOption(option_id="opt_a", text="So khớp với Query."),
        CheckOption(option_id="opt_b", text="Lưu dữ liệu."),
        CheckOption(option_id="opt_c", text="Tính điểm chú ý."),
    ]
    # "A" should match opt_a
    assert (
        evaluate_mcq_student_answer(
            student_answer="A",
            correct_option_id="opt_a",
            options=opts,
            expected_answer="So khớp với Query.",
        )
        is True
    )

    # "Đáp án A" should match opt_a
    assert (
        evaluate_mcq_student_answer(
            student_answer="Đáp án A",
            correct_option_id="opt_a",
            options=opts,
            expected_answer="So khớp với Query.",
        )
        is True
    )


def test_micro_check_validation_rules():
    # 2 options fails for MCQ
    with pytest.raises(ValidationError):
        MicroCheck(
            question="Key là gì?",
            question_type="multiple_choice",
            target_concept="Key",
            expected_answer="So khớp",
            correct_option_id="opt_a",
            options=[
                CheckOption(option_id="opt_a", text="So khớp"),
                CheckOption(option_id="opt_b", text="Lưu dữ liệu"),
            ],
            explanation="Giải thích",
            evidence=["Bằng chứng"],
        )

    # Duplicate option IDs fails
    with pytest.raises(ValidationError):
        MicroCheck(
            question="Key là gì?",
            question_type="multiple_choice",
            target_concept="Key",
            expected_answer="So khớp",
            correct_option_id="opt_a",
            options=[
                CheckOption(option_id="opt_a", text="So khớp"),
                CheckOption(option_id="opt_a", text="Lưu dữ liệu"),
                CheckOption(option_id="opt_c", text="Khác"),
            ],
            explanation="Giải thích",
            evidence=["Bằng chứng"],
        )

    # Invalid correct_option_id fails
    with pytest.raises(ValidationError):
        MicroCheck(
            question="Key là gì?",
            question_type="multiple_choice",
            target_concept="Key",
            expected_answer="So khớp",
            correct_option_id="opt_nonexistent",
            options=[
                CheckOption(option_id="opt_a", text="So khớp"),
                CheckOption(option_id="opt_b", text="Lưu dữ liệu"),
                CheckOption(option_id="opt_c", text="Khác"),
            ],
            explanation="Giải thích",
            evidence=["Bằng chứng"],
        )
