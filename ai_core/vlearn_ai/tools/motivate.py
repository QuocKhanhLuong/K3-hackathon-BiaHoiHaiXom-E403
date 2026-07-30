"""Pedagogical tool 5: motivate."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from vlearn_ai.prompts.pedagogical_tools import MOTIVATE_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, StrictBaseModel


class MotivateOutput(StrictBaseModel):
    """Output format for motivate tool."""

    message: str = Field(..., min_length=1)
    acknowledged_difficulty: str = Field(..., min_length=1)
    next_small_step: str = Field(..., min_length=1)


async def execute_motivate(
    difficulty: str,
    model: BaseChatModel,
) -> MotivateOutput:
    """Execute motivate tool using structured model output."""
    messages = [
        SystemMessage(content=MOTIVATE_PROMPT),
        HumanMessage(
            content=(
                f"Nội dung/khái niệm học viên đang gặp khó khăn:\n"
                f"<untrusted_student_query>\n{difficulty}\n</untrusted_student_query>"
            )
        ),
    ]

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(MotivateOutput)
            res = await structured.ainvoke(messages)
            if isinstance(res, MotivateOutput) and res.message.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"motivate structured output failed: {exc}"
        ) from exc

    try:
        raw_res = await model.ainvoke(messages)
        content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
        if isinstance(content, str) and content.strip():
            return MotivateOutput(
                message=content.strip(),
                acknowledged_difficulty=difficulty,
                next_small_step="Đọc lại định nghĩa ngắn gọn và thử làm câu hỏi kiểm tra lại nhé.",
            )
    except Exception as exc:
        raise AIStructuredOutputError(f"motivate invocation failed: {exc}") from exc

    raise AIStructuredOutputError("motivate failed to produce non-empty encouragement.")
