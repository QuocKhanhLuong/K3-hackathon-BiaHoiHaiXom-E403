"""Pedagogical tool 1: review_concept."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import REVIEW_CONCEPT_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, GroundedAnswer


async def execute_review_concept(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Execute review_concept tool using structured model output without secondary text fallback."""
    untrusted_payload = (
        f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
        f"Khái niệm cần giải thích/ôn tập:\n<untrusted_student_query>\n{query}\n</untrusted_student_query>"
    )
    messages = build_trusted_messages(REVIEW_CONCEPT_PROMPT, untrusted_payload)

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GroundedAnswer)
            res = await structured.ainvoke(messages)
            if isinstance(res, GroundedAnswer) and res.answer.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"review_concept structured output failed: {exc}"
        ) from exc

    raise AIStructuredOutputError(
        "review_concept failed to produce valid GroundedAnswer."
    )
