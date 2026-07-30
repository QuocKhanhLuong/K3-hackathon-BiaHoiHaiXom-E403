"""Pedagogical tool 1: review_concept."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from vlearn_ai.prompts.pedagogical_tools import REVIEW_CONCEPT_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, Citation, GroundedAnswer


async def execute_review_concept(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Execute review_concept tool using structured model output."""
    messages = [
        SystemMessage(content=REVIEW_CONCEPT_PROMPT),
        HumanMessage(
            content=(
                f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
                f"Khái niệm cần giải thích/ôn tập:\n<untrusted_student_query>\n{query}\n</untrusted_student_query>"
            )
        ),
    ]

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

    # Direct invoke attempt if with_structured_output fails to parse
    try:
        raw_res = await model.ainvoke(messages)
        content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
        if isinstance(content, str) and content.strip():
            snippet = context[:120].strip() if context else "Tài liệu học tập"
            return GroundedAnswer(
                answer=content.strip(),
                citations=[Citation(citation_id="ctx_1", snippet=snippet)],
            )
    except Exception as exc:
        raise AIStructuredOutputError(
            f"review_concept invocation failed: {exc}"
        ) from exc

    raise AIStructuredOutputError("review_concept failed to produce non-empty answer.")
