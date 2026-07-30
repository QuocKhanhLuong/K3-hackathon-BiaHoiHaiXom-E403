"""Workflow 5: Suggest follow-up questions."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.followups import (
    FOLLOWUPS_SYSTEM_PROMPT,
    FOLLOWUPS_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.schemas import AIStructuredOutputError, FollowUpSuggestions


async def run_suggest_followups(
    query: str,
    context: str,
    grounded_answer: str,
    model: BaseChatModel,
) -> FollowUpSuggestions:
    """Run suggest followups workflow without secondary raw text fallback."""
    untrusted_payload = FOLLOWUPS_USER_PROMPT_TEMPLATE.format(
        selected_context=context,
        user_query=query,
        grounded_answer=grounded_answer,
    )
    messages = build_trusted_messages(FOLLOWUPS_SYSTEM_PROMPT, untrusted_payload)

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(FollowUpSuggestions)
            res = await structured.ainvoke(messages)
            if isinstance(res, FollowUpSuggestions):
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"suggest_followups structured output failed: {exc}"
        ) from exc

    raise AIStructuredOutputError(
        "suggest_followups failed to produce valid FollowUpSuggestions."
    )
