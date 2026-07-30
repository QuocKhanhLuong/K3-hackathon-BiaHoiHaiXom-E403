"""Pedagogical tool 2: give_direct_answer."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import GIVE_DIRECT_ANSWER_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, GroundedAnswer


async def execute_give_direct_answer(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Execute give_direct_answer tool using structured model output without secondary text fallback."""
    untrusted_payload = (
        f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
        f"Câu hỏi sự thật:\n<untrusted_student_query>\n{query}\n</untrusted_student_query>"
    )
    messages = build_trusted_messages(GIVE_DIRECT_ANSWER_PROMPT, untrusted_payload)

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GroundedAnswer)
            res = await structured.ainvoke(messages)
            if isinstance(res, GroundedAnswer) and res.answer.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"give_direct_answer structured output failed: {exc}"
        ) from exc

    raise AIStructuredOutputError(
        "give_direct_answer failed to produce valid GroundedAnswer."
    )
