"""Pedagogical tool 6: validate_understanding (generate check & evaluate answer)."""

import re
from typing import Literal

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
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
    previous_check: MicroCheck | None = None,
) -> MicroCheck | CheckEvaluation:
    """Execute validate_understanding tool in generate or evaluate mode."""
    if mode == "generate_check":
        prev_text = (
            f"\nCâu hỏi cũ (hãy tạo câu hỏi khác hẳn, không lặp lại):\n{previous_check.question}"
            if previous_check
            else ""
        )
        untrusted_payload = (
            CHECK_GENERATE_USER_PROMPT_TEMPLATE.format(
                selected_context=context,
                grounded_answer=grounded_answer,
            )
            + prev_text
        )

        messages = build_trusted_messages(
            CHECK_GENERATE_SYSTEM_PROMPT, untrusted_payload
        )

        try:
            if hasattr(model, "with_structured_output"):
                structured = model.with_structured_output(MicroCheck)
                res = await structured.ainvoke(messages)
                if isinstance(res, MicroCheck):
                    if previous_check and _normalize_text(
                        res.question
                    ) == _normalize_text(previous_check.question):
                        raise AIStructuredOutputError(
                            "Generated check is an exact duplicate of previous check."
                        )
                    return res
        except Exception as exc:
            raise AIStructuredOutputError(
                f"generate_check structured output failed: {exc}"
            ) from exc

        raise AIStructuredOutputError(
            "generate_check failed to produce valid MicroCheck."
        )

    else:
        # evaluate_answer mode
        is_mcq_correct = evaluate_mcq_student_answer(
            student_answer=student_answer,
            correct_option_id=correct_option_id,
            options=options or [],
            expected_answer=expected_answer,
        )

        untrusted_payload = MISCONCEPTION_USER_PROMPT_TEMPLATE.format(
            question=question,
            expected_answer=expected_answer,
            selected_context=context,
            student_answer=student_answer,
        )
        messages = build_trusted_messages(
            MISCONCEPTION_SYSTEM_PROMPT, untrusted_payload
        )

        try:
            if hasattr(model, "with_structured_output"):
                structured = model.with_structured_output(CheckEvaluation)
                res = await structured.ainvoke(messages)
                if isinstance(res, CheckEvaluation):
                    # Enforce deterministic evaluation override for correct MCQ answers
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

        raise AIStructuredOutputError(
            "evaluate_answer failed to produce valid CheckEvaluation."
        )
