"""Workflow module: check understanding."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.schemas import MicroCheck
from vlearn_ai.tools.validate_understanding import execute_validate_understanding


async def run_check_understanding(
    context: str,
    grounded_answer: str,
    model: BaseChatModel,
) -> MicroCheck:
    """Generate micro-check using validate_understanding tool in generate_check mode."""
    res = await execute_validate_understanding(
        mode="generate_check",
        context=context,
        grounded_answer=grounded_answer,
        model=model,
    )
    if isinstance(res, MicroCheck):
        return res

    return MicroCheck(
        question="Phát biểu nào mô tả đúng nhất về nội dung vừa học?",
        question_type="multiple_choice",
        target_concept="core_concept",
        expected_answer="Lựa chọn A đúng theo tài liệu.",
        options=["Lựa chọn A đúng theo tài liệu.", "Lựa chọn B mô tả sai."],
        explanation="Căn cứ theo bài học.",
        evidence=[context[:100]] if context else [],
    )
