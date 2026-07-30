"""Pedagogical tool 4: give_hint."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from vlearn_ai.prompts.pedagogical_tools import GIVE_HINT_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, StrictBaseModel


class GiveHintOutput(StrictBaseModel):
    """Output format for give_hint tool."""

    hint: str = Field(..., min_length=1)
    hint_level: int = Field(default=1, ge=1, le=3)
    guiding_question: str = Field(..., min_length=1)


async def execute_give_hint(
    concept: str,
    context: str,
    hint_level: int,
    model: BaseChatModel,
) -> GiveHintOutput:
    """Execute give_hint tool using structured model output."""
    messages = [
        SystemMessage(content=GIVE_HINT_PROMPT),
        HumanMessage(
            content=(
                f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
                f"Cấp độ gợi ý (1-3): {hint_level}\n"
                f"Khái niệm cần gợi ý:\n<untrusted_student_query>\n{concept}\n</untrusted_student_query>"
            )
        ),
    ]

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GiveHintOutput)
            res = await structured.ainvoke(messages)
            if isinstance(res, GiveHintOutput) and res.hint.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"give_hint structured output failed: {exc}"
        ) from exc

    try:
        raw_res = await model.ainvoke(messages)
        content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
        if isinstance(content, str) and content.strip():
            return GiveHintOutput(
                hint=content.strip(),
                hint_level=hint_level,
                guiding_question="Bạn nghĩ khái niệm này có vai trò gì trong bài học?",
            )
    except Exception as exc:
        raise AIStructuredOutputError(f"give_hint invocation failed: {exc}") from exc

    raise AIStructuredOutputError("give_hint failed to produce non-empty hint.")
