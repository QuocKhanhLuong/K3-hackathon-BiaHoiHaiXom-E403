"""Pedagogical tool 4: give_hint."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import GIVE_HINT_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, GiveHintOutput


async def execute_give_hint(
    concept: str,
    context: str,
    hint_level: int,
    model: BaseChatModel,
) -> GiveHintOutput:
    """Execute give_hint tool using structured model output without secondary text fallback."""
    untrusted_payload = (
        f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
        f"Cấp độ gợi ý (1-3): {hint_level}\n"
        f"Khái niệm cần gợi ý:\n<untrusted_student_query>\n{concept}\n</untrusted_student_query>"
    )
    messages = build_trusted_messages(GIVE_HINT_PROMPT, untrusted_payload)

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

    raise AIStructuredOutputError("give_hint failed to produce valid GiveHintOutput.")
