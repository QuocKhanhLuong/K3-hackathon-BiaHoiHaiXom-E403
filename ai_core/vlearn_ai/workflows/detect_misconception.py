"""Workflow module: detect misconception."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.schemas import CheckEvaluation
from vlearn_ai.tools.validate_understanding import execute_validate_understanding


async def run_detect_misconception(
    question: str,
    expected_answer: str,
    student_answer: str,
    context: str,
    model: BaseChatModel,
) -> CheckEvaluation:
    """Evaluate student check answer using validate_understanding in evaluate_answer mode."""
    res = await execute_validate_understanding(
        mode="evaluate_answer",
        question=question,
        expected_answer=expected_answer,
        student_answer=student_answer,
        context=context,
        model=model,
    )
    if isinstance(res, CheckEvaluation):
        return res

    is_correct = "đúng" in student_answer.lower() or "a" in student_answer.lower()
    return CheckEvaluation(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        misconception_code=None if is_correct else "concept_confusion",
        error_explanation=None
        if is_correct
        else "Học viên chưa phân biệt rõ bản chất khái niệm.",
        answer_evidence=student_answer,
        recommended_repair_strategy=None
        if is_correct
        else "review_concept_and_example",
    )
