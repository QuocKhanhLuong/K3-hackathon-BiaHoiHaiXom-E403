"""Workflow 5: Suggest follow-ups."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from vlearn_ai.prompts.followups import (
    FOLLOWUPS_SYSTEM_PROMPT,
    FOLLOWUPS_USER_PROMPT_TEMPLATE,
)
from vlearn_ai.schemas import AIStructuredOutputError, FollowUp, FollowUpSuggestions


async def run_suggest_followups(
    query: str,
    context: str,
    grounded_answer: str,
    model: BaseChatModel,
) -> FollowUpSuggestions:
    """Run suggest followups workflow."""
    messages = [
        SystemMessage(content=FOLLOWUPS_SYSTEM_PROMPT),
        HumanMessage(
            content=FOLLOWUPS_USER_PROMPT_TEMPLATE.format(
                user_query=query,
                selected_context=context,
                grounded_answer=grounded_answer,
            )
        ),
    ]

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(FollowUpSuggestions)
            res = await structured.ainvoke(messages)
            if isinstance(res, FollowUpSuggestions) and len(res.followups) >= 2:
                return res
    except Exception as exc:
        raise AIStructuredOutputError(
            f"run_suggest_followups structured output failed: {exc}"
        ) from exc

    try:
        await model.ainvoke(messages)
    except Exception as exc:
        raise AIStructuredOutputError(
            f"run_suggest_followups invocation failed: {exc}"
        ) from exc

    q_clean = query[:30] if query else "khái niệm"
    return FollowUpSuggestions(
        followups=[
            FollowUp(
                label="Hiểu cơ chế sâu hơn",
                question=f"Cơ chế chi tiết của '{q_clean}' là gì?",
            ),
            FollowUp(
                label="Xem ví dụ thực tế",
                question="Cho thêm ví dụ ứng dụng thực tế của phần này.",
            ),
        ]
    )
