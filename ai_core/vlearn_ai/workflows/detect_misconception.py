"""Workflow 3: Detect misconception."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.schemas import CheckEvaluation, CheckOption
from vlearn_ai.tools.validate_understanding import execute_validate_understanding


async def run_detect_misconception(
    question: str,
    expected_answer: str,
    student_answer: str,
    context: str,
    model: BaseChatModel,
    correct_option_id: str | None = None,
    options: list[CheckOption] | None = None,
) -> CheckEvaluation:
    """Run detect misconception workflow in evaluate mode."""
    res = await execute_validate_understanding(
        mode="evaluate_answer",
        question=question,
        expected_answer=expected_answer,
        student_answer=student_answer,
        context=context,
        correct_option_id=correct_option_id,
        options=options,
        model=model,
    )
    if isinstance(res, CheckEvaluation):
        return res
    raise ValueError("Expected CheckEvaluation from execute_validate_understanding.")
