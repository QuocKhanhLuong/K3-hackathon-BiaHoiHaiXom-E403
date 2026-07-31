"""Pedagogical tool: give_general_answer."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import GENERAL_KNOWLEDGE_ANSWER_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, GeneralAnswer


async def execute_give_general_answer(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GeneralAnswer:
    """Execute give_general_answer tool for out-of-context queries."""
    untrusted_payload = (
        f"Bối cảnh bài học (để tham khảo chủ đề, KHÔNG bắt buộc trích dẫn):\n<course_context>\n{context}\n</course_context>\n\n"
        f"Câu hỏi của học viên:\n<student_query>\n{query}\n</student_query>"
    )
    messages = build_trusted_messages(GENERAL_KNOWLEDGE_ANSWER_PROMPT, untrusted_payload)

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GeneralAnswer)
            res = await structured.ainvoke(messages)
            if isinstance(res, GeneralAnswer) and res.answer.strip():
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"give_general_answer structured output failed: {exc}"
        ) from exc

    raise AIStructuredOutputError(
        "give_general_answer failed to produce valid GeneralAnswer."
    )
