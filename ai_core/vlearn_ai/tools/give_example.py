"""Pedagogical tool 3: give_example."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

from vlearn_ai.prompts.pedagogical_tools import GIVE_EXAMPLE_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, StrictBaseModel


class GiveExampleOutput(StrictBaseModel):
    """Output format for give_example tool."""

    example: str = Field(..., min_length=1)
    relevance_explanation: str = Field(..., min_length=1)


async def execute_give_example(
    concept: str,
    context: str,
    model: BaseChatModel,
) -> GiveExampleOutput:
    """Execute give_example tool using structured model output."""
    messages = [
        SystemMessage(content=GIVE_EXAMPLE_PROMPT),
        HumanMessage(
            content=(
                f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
                f"Khái niệm cần ví dụ minh họa:\n<untrusted_student_query>\n{concept}\n</untrusted_student_query>"
            )
        ),
    ]

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GiveExampleOutput)
            res = await structured.ainvoke(messages)
            if isinstance(res, GiveExampleOutput) and res.example.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"give_example structured output failed: {exc}"
        ) from exc

    try:
        raw_res = await model.ainvoke(messages)
        content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
        if isinstance(content, str) and content.strip():
            return GiveExampleOutput(
                example=content.strip(),
                relevance_explanation="Ví dụ minh họa cho khái niệm trong bối cảnh bài học.",
            )
    except Exception as exc:
        raise AIStructuredOutputError(f"give_example invocation failed: {exc}") from exc

    raise AIStructuredOutputError("give_example failed to produce non-empty example.")
