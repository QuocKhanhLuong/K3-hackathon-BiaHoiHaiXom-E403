"""Pedagogical tool 6: validate_understanding (generate check & evaluate answer)."""

import hashlib
import re
import uuid
from difflib import SequenceMatcher
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


MCQAnswerMatch = Literal[
    "recognized_correct", "recognized_incorrect", "unrecognized"
]


def classify_mcq_student_answer(
    student_answer: str,
    correct_option_id: str | None,
    options: list[CheckOption],
    expected_answer: str,
) -> MCQAnswerMatch:
    """Classify a recognized MCQ selection without relying on the LLM."""
    ans_norm = _normalize_text(student_answer)
    exp_norm = _normalize_text(expected_answer)

    # 1. Exact text match with expected answer
    if ans_norm == exp_norm:
        return "recognized_correct"

    # 2. Check if student entered explicit option ID (e.g. "opt_a", "opt_b")
    for opt in options:
        if ans_norm == _normalize_text(opt.option_id):
            return (
                "recognized_correct"
                if correct_option_id and opt.option_id == correct_option_id
                else "recognized_incorrect"
            )

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
                return "recognized_correct"
            if _normalize_text(chosen_opt.text) == exp_norm:
                return "recognized_correct"
            return "recognized_incorrect"

    # 4. Check if student typed text matching the correct option's text
    for opt in options:
        opt_text_norm = _normalize_text(opt.text)
        if ans_norm == opt_text_norm:
            if correct_option_id and opt.option_id == correct_option_id:
                return "recognized_correct"
            if opt_text_norm == exp_norm:
                return "recognized_correct"
            return "recognized_incorrect"

    return "unrecognized"


def evaluate_mcq_student_answer(
    student_answer: str,
    correct_option_id: str | None,
    options: list[CheckOption],
    expected_answer: str,
) -> bool:
    """Backwards-compatible boolean helper for deterministic correct matches."""
    return (
        classify_mcq_student_answer(
            student_answer=student_answer,
            correct_option_id=correct_option_id,
            options=options,
            expected_answer=expected_answer,
        )
        == "recognized_correct"
    )


def build_check_generation_signature(check: MicroCheck) -> str:
    """Build a stable, server-owned signature for check observability."""
    canonical = "|".join(
        [
            _normalize_text(check.target_concept),
            _normalize_text(check.expected_answer),
            _normalize_text(check.question),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def _token_similarity(left: str, right: str) -> float:
    """Return Jaccard similarity over normalized semantic tokens."""
    left_tokens = set(re.findall(r"\w+", _normalize_text(left), flags=re.UNICODE))
    right_tokens = set(re.findall(r"\w+", _normalize_text(right), flags=re.UNICODE))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def are_semantically_duplicate_checks(
    previous: MicroCheck,
    candidate: MicroCheck,
) -> bool:
    """Reject exact and near-paraphrase checks of the same concept."""
    previous_question = _normalize_text(previous.question)
    candidate_question = _normalize_text(candidate.question)
    if previous_question == candidate_question:
        return True

    same_target = _normalize_text(previous.target_concept) == _normalize_text(
        candidate.target_concept
    )
    same_answer = _normalize_text(previous.expected_answer) == _normalize_text(
        candidate.expected_answer
    )
    sequence_similarity = SequenceMatcher(
        None, previous_question, candidate_question
    ).ratio()
    token_similarity = _token_similarity(previous_question, candidate_question)

    if sequence_similarity >= 0.88 or token_similarity >= 0.80:
        return same_target or same_answer
    return same_target and same_answer and (
        sequence_similarity >= 0.58 or token_similarity >= 0.55
    )


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
        rejected_question: str | None = None
        for generation_attempt in range(3):
            previous_text = (
                "\nCâu hỏi cũ (hãy đổi góc kiểm tra, không chỉ diễn đạt lại):"
                f"\n{previous_check.question}"
                if previous_check
                else ""
            )
            rejected_text = (
                "\nCâu vừa bị từ chối vì trùng nghĩa, không được dùng lại:"
                f"\n{rejected_question}"
                if rejected_question
                else ""
            )
            untrusted_payload = (
                CHECK_GENERATE_USER_PROMPT_TEMPLATE.format(
                    selected_context=context,
                    grounded_answer=grounded_answer,
                )
                + previous_text
                + rejected_text
            )
            messages = build_trusted_messages(
                CHECK_GENERATE_SYSTEM_PROMPT, untrusted_payload
            )

            try:
                if hasattr(model, "with_structured_output"):
                    structured = model.with_structured_output(MicroCheck)
                    res = await structured.ainvoke(messages)
                    if isinstance(res, MicroCheck):
                        res.check_id = uuid.uuid4().hex
                        res.generation_signature = build_check_generation_signature(res)
                        if previous_check and are_semantically_duplicate_checks(
                            previous_check, res
                        ):
                            rejected_question = res.question
                            continue
                        return res
            except AIStructuredOutputError:
                raise
            except Exception as exc:
                raise AIStructuredOutputError(
                    f"generate_check structured output failed: {exc}"
                ) from exc

        raise AIStructuredOutputError(
            "generate_check failed to produce a valid non-duplicate MicroCheck."
        )

    else:
        # evaluate_answer mode
        mcq_match: MCQAnswerMatch = "unrecognized"
        if correct_option_id and options:
            mcq_match = classify_mcq_student_answer(
                student_answer=student_answer,
                correct_option_id=correct_option_id,
                options=options,
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
                    llm_marked_correct = res.is_correct
                    if mcq_match == "recognized_correct":
                        res.is_correct = True
                        res.score = 1.0
                        res.misconception_code = "none"
                        res.recommended_repair_strategy = "none"
                        res.evaluation_source = "deterministic_mcq"
                    elif mcq_match == "recognized_incorrect":
                        res.is_correct = False
                        res.score = 0.0
                        res.evaluation_source = "deterministic_mcq"
                        if res.misconception_code == "none":
                            res.misconception_code = "incorrect_option"
                        if res.recommended_repair_strategy == "none":
                            res.recommended_repair_strategy = (
                                "review_concept_and_example"
                            )
                        if llm_marked_correct:
                            res.error_explanation = (
                                "Lựa chọn của học viên không khớp với đáp án đúng."
                            )
                    else:
                        res.evaluation_source = "llm_semantic"
                    return res
        except Exception as exc:
            raise AIStructuredOutputError(
                f"evaluate_answer structured output failed: {exc}"
            ) from exc

        raise AIStructuredOutputError(
            "evaluate_answer failed to produce valid CheckEvaluation."
        )
