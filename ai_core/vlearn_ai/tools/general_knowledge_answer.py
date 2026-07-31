"""Controlled model-knowledge answer tool with no course citations."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.prompts.pedagogical_tools import GENERAL_KNOWLEDGE_ANSWER_PROMPT
from vlearn_ai.schemas import AIStructuredOutputError, GeneralKnowledgeAnswer


async def execute_general_knowledge_answer(
    query: str, model: BaseChatModel
) -> GeneralKnowledgeAnswer:
    """Answer a pre-approved standalone question without passing course context."""
    payload = f"<untrusted_student_query>\n{query}\n</untrusted_student_query>"
    messages = build_trusted_messages(GENERAL_KNOWLEDGE_ANSWER_PROMPT, payload)
    try:
        if hasattr(model, "with_structured_output"):
            result = await model.with_structured_output(GeneralKnowledgeAnswer).ainvoke(
                messages
            )
            if isinstance(result, GeneralKnowledgeAnswer) and result.answer.strip():
                return result
    except Exception as exc:
        raise AIStructuredOutputError(
            f"general_knowledge_answer structured output failed: {exc}"
        ) from exc
    raise AIStructuredOutputError(
        "general_knowledge_answer failed to produce structured output."
    )
