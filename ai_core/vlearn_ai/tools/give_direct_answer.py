"""Pedagogical tool 2: give_direct_answer."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from vlearn_ai.prompts.pedagogical_tools import GIVE_DIRECT_ANSWER_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, Citation, GroundedAnswer


async def execute_give_direct_answer(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Execute give_direct_answer tool using structured model output."""
    messages = [
        SystemMessage(content=GIVE_DIRECT_ANSWER_PROMPT),
        HumanMessage(
            content=(
                f"Bối cảnh bài học:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
                f"Câu hỏi sự thật:\n<untrusted_student_query>\n{query}\n</untrusted_student_query>"
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
            f"give_direct_answer structured output failed: {exc}"
        ) from exc

    try:
        raw_res = await model.ainvoke(messages)
        content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
        if isinstance(content, str) and content.strip():
            snippet = context[:120].strip() if context else "Tài liệu bài học"
            return GroundedAnswer(
                answer=content.strip(),
                citations=[Citation(citation_id="ctx_1", snippet=snippet)],
            )
    except Exception as exc:
        raise AIStructuredOutputError(
            f"give_direct_answer invocation failed: {exc}"
        ) from exc

    raise AIStructuredOutputError(
        "give_direct_answer failed to produce non-empty answer."
    )
