"""Pedagogical tool 5: motivate."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import MOTIVATE_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, MotivateOutput


async def execute_motivate(
    difficulty: str,
    model: BaseChatModel,
) -> MotivateOutput:
    """Execute motivate tool using structured model output without secondary text fallback."""
    untrusted_payload = (
        f"Nội dung/khái niệm học viên đang gặp khó khăn:\n"
        f"<untrusted_student_query>\n{difficulty}\n</untrusted_student_query>"
    )
    messages = build_trusted_messages(MOTIVATE_PROMPT, untrusted_payload)

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

    raise AIStructuredOutputError("motivate failed to produce valid MotivateOutput.")
