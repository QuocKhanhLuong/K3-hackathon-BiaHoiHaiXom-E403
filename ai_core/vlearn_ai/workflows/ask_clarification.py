"""Workflow 1: Ask clarification."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.clarification import (
    CLARIFICATION_SYSTEM_PROMPT,
    CLARIFICATION_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.schemas import AIStructuredOutputError, ClarificationRequest


async def run_ask_clarification(
    query: str,
    context: str,
    model: BaseChatModel,
) -> ClarificationRequest:
    """Run ask clarification workflow without secondary raw text fallback."""
    untrusted_payload = CLARIFICATION_USER_PROMPT_TEMPLATE.format(
        selected_context=context, user_query=query
    )
    messages = build_trusted_messages(CLARIFICATION_SYSTEM_PROMPT, untrusted_payload)

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

    raise AIStructuredOutputError(
        "run_ask_clarification failed to produce valid ClarificationRequest."
    )
