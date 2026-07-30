"""Workflow module: ask clarification."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.clarification import (
    CLARIFICATION_SYSTEM_PROMPT,
    CLARIFICATION_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.schemas import ClarificationRequest


async def run_ask_clarification(
    query: str,
    context: str,
    model: BaseChatModel,
) -> ClarificationRequest:
    """Generate a clarification request when query or context is ambiguous."""
    user_prompt = CLARIFICATION_USER_PROMPT_TEMPLATE.format(
        selected_context=context,
        user_query=query,
    )
    full_prompt = f"{CLARIFICATION_SYSTEM_PROMPT}\n\n{user_prompt}"

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(ClarificationRequest)
            res = await structured.ainvoke(full_prompt)
            if isinstance(res, ClarificationRequest):
                return res
    except (AttributeError, ValueError, TypeError, RuntimeError):
        pass

    return ClarificationRequest(
        clarification_question="Bạn có thể làm rõ hơn bạn đang muốn tìm hiểu khía cạnh nào trong bài học này không?",
        reason="Câu hỏi ban đầu chưa đủ thông tin chi tiết.",
    )
