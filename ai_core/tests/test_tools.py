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
    are_semantically_duplicate_checks,
    classify_mcq_student_answer,
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


def test_mcq_classification_recognizes_incorrect_option():
    opts = [
        CheckOption(option_id="opt_a", text="So khớp với Query."),
        CheckOption(option_id="opt_b", text="Lưu dữ liệu."),
        CheckOption(option_id="opt_c", text="Tính điểm chú ý."),
    ]

    assert (
        classify_mcq_student_answer(
            student_answer="opt_b",
            correct_option_id="opt_a",
            options=opts,
            expected_answer="So khớp với Query.",
        )
        == "recognized_incorrect"
    )
    assert (
        classify_mcq_student_answer(
            student_answer="mình chưa chắc",
            correct_option_id="opt_a",
            options=opts,
            expected_answer="So khớp với Query.",
        )
        == "unrecognized"
    )


@pytest.mark.asyncio
async def test_mcq_recognized_wrong_option_overrides_llm_correct_result():
    opts = [
        CheckOption(option_id="opt_a", text="So khớp với Query."),
        CheckOption(option_id="opt_b", text="Lưu dữ liệu."),
        CheckOption(option_id="opt_c", text="Tính điểm chú ý."),
    ]
    fake_llm = DeterministicFakeChatModel(misconception_to_return=False)

    result = await execute_validate_understanding(
        mode="evaluate_answer",
        question="Key dùng để làm gì?",
        expected_answer="So khớp với Query.",
        student_answer="opt_b",
        correct_option_id="opt_a",
        options=opts,
        context="Key dùng để so khớp với Query.",
        model=fake_llm,
    )

    assert result.is_correct is False
    assert result.score == 0.0
    assert result.misconception_code == "incorrect_option"
    assert result.evaluation_source == "deterministic_mcq"


def test_semantic_duplicate_check_detection():
    previous = MicroCheck(
        question="Key có vai trò gì trong cơ chế attention?",
        question_type="multiple_choice",
        target_concept="Transformer Key",
        expected_answer="Key dùng để so khớp với Query.",
        correct_option_id="opt_a",
        options=[
            CheckOption(option_id="opt_a", text="So khớp với Query."),
            CheckOption(option_id="opt_b", text="Lưu nội dung."),
            CheckOption(option_id="opt_c", text="Tạo đầu ra."),
        ],
        explanation="Key được so khớp với Query.",
        evidence=["Key dùng để so khớp với Query."],
    )
    paraphrase = previous.model_copy(
        update={"question": "Trong attention, Key có vai trò gì?"}
    )
    different_angle = previous.model_copy(
        update={
            "question": "Điều gì xảy ra nếu hai Key giống hệt nhau?",
            "expected_answer": "Hai Key có thể nhận điểm tương quan tương tự.",
        }
    )

    assert are_semantically_duplicate_checks(previous, paraphrase) is True
    assert are_semantically_duplicate_checks(previous, different_angle) is False


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


def test_grounding_unsupported_extra_sentence_fails():
    from vlearn_ai.guardrails.grounding_guard import verify_grounding
    from vlearn_ai.schemas import Citation, GroundedClaim

    ctx = '[source source_id="c1"]\nKey dùng để so khớp với Query trong Transformer.'
    cits = [
        Citation(
            citation_id="c1", snippet="Key dùng để so khớp với Query trong Transformer."
        )
    ]
    claims = [
        GroundedClaim(claim="Key dùng để so khớp với Query.", citation_ids=["c1"])
    ]
    ans = "Key dùng để so khớp với Query. Thích dùng GPU vì nó tính toán nhanh vèo vèo không có trong tài liệu."
    valid, err = verify_grounding(ans, cits, ctx, claims)
    assert valid is False
    assert "not covered" in err.lower() or "unsupported" in err.lower()


def test_grounding_unknown_citation_id_fails():
    from vlearn_ai.guardrails.grounding_guard import verify_grounding
    from vlearn_ai.schemas import Citation, GroundedClaim

    ctx = '[source source_id="c1"]\nKey dùng để so khớp với Query.'
    cits = [Citation(citation_id="c1", snippet="Key dùng để so khớp với Query.")]
    claims = [
        GroundedClaim(claim="Key dùng để so khớp với Query.", citation_ids=["c99"])
    ]
    valid, err = verify_grounding("Key dùng để so khớp với Query.", cits, ctx, claims)
    assert valid is False
    assert "unknown citation id" in err.lower()


def test_grounding_claim_not_supported_fails():
    from vlearn_ai.guardrails.grounding_guard import verify_grounding
    from vlearn_ai.schemas import Citation, GroundedClaim

    ctx = '[source source_id="c1"]\nKey dùng để so khớp với Query.'
    cits = [Citation(citation_id="c1", snippet="Key dùng để so khớp với Query.")]
    claims = [
        GroundedClaim(claim="Value lưu giữ thông tin kết quả.", citation_ids=["c1"])
    ]
    valid, err = verify_grounding("Value lưu giữ thông tin kết quả.", cits, ctx, claims)
    assert valid is False
    assert "not supported" in err.lower()


def test_grounding_stale_citations_after_repair_fails():
    from vlearn_ai.guardrails.grounding_guard import verify_grounding
    from vlearn_ai.schemas import Citation, GroundedClaim

    ctx = '[source source_id="c1"]\nKey dùng để so khớp với Query.'
    # Stale citations from previous turn don't match the new claims
    cits = [Citation(citation_id="c1", snippet="Key dùng để so khớp với Query.")]
    claims = [
        GroundedClaim(claim="Khái niệm mới được giảng giải.", citation_ids=["c1"])
    ]
    valid, _err = verify_grounding("Khái niệm mới được giảng giải.", cits, ctx, claims)
    assert valid is False


def test_grounding_fully_grounded_multi_claim_passes():
    from vlearn_ai.guardrails.grounding_guard import verify_grounding
    from vlearn_ai.schemas import Citation, GroundedClaim

    ctx = ('[source source_id="c1"]\nKey dùng để so khớp với Query.\n'
           '[source source_id="c2"]\nValue chứa thông tin nội dung.')
    cits = [
        Citation(citation_id="c1", snippet="Key dùng để so khớp với Query."),
        Citation(citation_id="c2", snippet="Value chứa thông tin nội dung."),
    ]
    claims = [
        GroundedClaim(claim="Key dùng để so khớp với Query.", citation_ids=["c1"]),
        GroundedClaim(claim="Value chứa thông tin nội dung.", citation_ids=["c2"]),
    ]
    ans = "Key dùng để so khớp với Query. Value chứa thông tin nội dung."
    valid, err = verify_grounding(ans, cits, ctx, claims)
    assert valid is True
    assert err is None
