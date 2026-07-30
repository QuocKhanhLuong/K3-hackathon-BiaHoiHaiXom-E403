"""Pedagogical tool 6: validate_understanding (generate check & evaluate answer)."""

import re
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from vlearn_ai.prompts.misconception import (
    MISCONCEPTION_SYSTEM_PROMPT,
    MISCONCEPTION_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.prompts.understanding_check import (
    CHECK_GENERATE_SYSTEM_PROMPT,
    CHECK_GENERATE_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.schemas import (
    AIStructuredOutputError,
    CheckEvaluation,
    CheckOption,
    MicroCheck,
)


def _normalize_text(text: str) -> str:
    """Normalize text for exact comparisons."""
    text = text.strip().lower()
    return re.sub(r"\s+", " ", text)


def evaluate_mcq_student_answer(
    student_answer: str,
    correct_option_id: str | None,
    options: list[CheckOption],
    expected_answer: str,
) -> bool:
    """Evaluate MCQ student answer deterministically without false-positive substring matching."""
    ans_norm = _normalize_text(student_answer)
    exp_norm = _normalize_text(expected_answer)

    # 1. Exact text match with expected answer
    if ans_norm == exp_norm:
        return True

    # 2. Check if student entered explicit option ID (e.g. "opt_a", "opt_b")
    if correct_option_id and ans_norm == _normalize_text(correct_option_id):
        return True

    # 3. Check option labels/texts
    opt_letter_map = {"a": 0, "b": 1, "c": 2, "d": 3}

    # Match standalone option letter or label (e.g., "a", "A", "lựa chọn a", "đáp án a")
    match_letter = re.match(
        r"^(?:lựa chọn|đáp án|câu|phương án)?\s*([abcd])(?:\s*đúng|\s*chính xác)?\.?$",
        ans_norm,
    )
    if match_letter:
        chosen_letter = match_letter.group(1)
        chosen_idx = opt_letter_map.get(chosen_letter)
        if chosen_idx is not None and chosen_idx < len(options):
            chosen_opt = options[chosen_idx]
            if correct_option_id and chosen_opt.option_id == correct_option_id:
                return True
            if _normalize_text(chosen_opt.text) == exp_norm:
                return True

    # 4. Check if student typed text matching the correct option's text
    for opt in options:
        opt_text_norm = _normalize_text(opt.text)
        if ans_norm == opt_text_norm:
            if correct_option_id and opt.option_id == correct_option_id:
                return True
            if opt_text_norm == exp_norm:
                return True

    return False


async def execute_validate_understanding(
    mode: Literal["generate_check", "evaluate_answer"],
    model: BaseChatModel,
    context: str = "",
    grounded_answer: str = "",
    question: str = "",
    expected_answer: str = "",
    student_answer: str = "",
    correct_option_id: str | None = None,
    options: list[CheckOption] | None = None,
) -> MicroCheck | CheckEvaluation:
    """Execute validate_understanding tool in generate or evaluate mode."""
    if mode == "generate_check":
        messages = [
            SystemMessage(content=CHECK_GENERATE_SYSTEM_PROMPT),
            HumanMessage(
                content=CHECK_GENERATE_USER_PROMPT_TEMPLATE.format(
                    selected_context=context,
                    grounded_answer=grounded_answer,
                )
            ),
        ]

        try:
            if hasattr(model, "with_structured_output"):
                structured = model.with_structured_output(MicroCheck)
                res = await structured.ainvoke(messages)
                if isinstance(res, MicroCheck):
                    return res
        except Exception as exc:
            raise AIStructuredOutputError(
                f"generate_check structured output failed: {exc}"
            ) from exc

        try:
            raw_res = await model.ainvoke(messages)
            content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
            return MicroCheck(
                question=str(content).strip()
                or "Khái niệm này có ý nghĩa gì trong bài học?",
                question_type="multiple_choice",
                target_concept="core_concept",
                expected_answer="Lựa chọn A là đáp án chính xác.",
                correct_option_id="opt_a",
                options=[
                    CheckOption(
                        option_id="opt_a", text="Lựa chọn A là đáp án chính xác."
                    ),
                    CheckOption(
                        option_id="opt_b", text="Lựa chọn B mô tả sai bài học."
                    ),
                    CheckOption(option_id="opt_c", text="Lựa chọn C không liên quan."),
                ],
                explanation="Giải thích đáp án đúng.",
                evidence=[context[:100]] if context else [],
            )
        except Exception as exc:
            raise AIStructuredOutputError(
                f"generate_check invocation failed: {exc}"
            ) from exc

    else:
        # evaluate_answer mode
        is_mcq_correct = evaluate_mcq_student_answer(
            student_answer=student_answer,
            correct_option_id=correct_option_id,
            options=options or [],
            expected_answer=expected_answer,
        )

        messages = [
            SystemMessage(content=MISCONCEPTION_SYSTEM_PROMPT),
            HumanMessage(
                content=MISCONCEPTION_USER_PROMPT_TEMPLATE.format(
                    question=question,
                    expected_answer=expected_answer,
                    selected_context=context,
                    student_answer=student_answer,
                )
            ),
        ]

        try:
            if hasattr(model, "with_structured_output"):
                structured = model.with_structured_output(CheckEvaluation)
                res = await structured.ainvoke(messages)
                if isinstance(res, CheckEvaluation):
                    # Override is_correct if deterministic evaluation succeeded
                    if is_mcq_correct:
                        res.is_correct = True
                        res.score = 1.0
                        res.misconception_code = "none"
                        res.recommended_repair_strategy = "none"
                    return res
        except Exception as exc:
            raise AIStructuredOutputError(
                f"evaluate_answer structured output failed: {exc}"
            ) from exc

        # Fallback deterministic evaluation if model fails
        if is_mcq_correct:
            return CheckEvaluation(
                is_correct=True,
                score=1.0,
                misconception_code="none",
                error_explanation="Học viên trả lời đúng.",
                answer_evidence=student_answer,
                recommended_repair_strategy="none",
            )
        else:
            return CheckEvaluation(
                is_correct=False,
                score=0.0,
                misconception_code="concept_confusion",
                error_explanation="Học viên trả lời chưa chính xác so với bối cảnh bài học.",
                answer_evidence=student_answer,
                recommended_repair_strategy="review_concept_and_example",
            )
