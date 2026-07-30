"""Workflow 1: Ask clarification."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from vlearn_ai.prompts.clarification import (
    CLARIFICATION_SYSTEM_PROMPT,
    CLARIFICATION_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.schemas import AIStructuredOutputError, ClarificationRequest


async def run_ask_clarification(
    query: str,
    context: str,
    model: BaseChatModel,
) -> ClarificationRequest:
    """Run ask clarification workflow."""
    messages = [
        SystemMessage(content=CLARIFICATION_SYSTEM_PROMPT),
        HumanMessage(
            content=CLARIFICATION_USER_PROMPT_TEMPLATE.format(
                selected_context=context, user_query=query
            )
        ),
    ]

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(ClarificationRequest)
            res = await structured.ainvoke(messages)
            if isinstance(res, ClarificationRequest):
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"run_ask_clarification structured output failed: {exc}"
        ) from exc

    try:
        raw_res = await model.ainvoke(messages)
        content = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
        return ClarificationRequest(
            clarification_question=str(content).strip()
            or "Bạn có thể làm rõ hơn khía cạnh bạn muốn tìm hiểu không?",
            reason="Ambiguous student query",
        )
    except Exception as exc:
        raise AIStructuredOutputError(
            f"run_ask_clarification invocation failed: {exc}"
        ) from exc
