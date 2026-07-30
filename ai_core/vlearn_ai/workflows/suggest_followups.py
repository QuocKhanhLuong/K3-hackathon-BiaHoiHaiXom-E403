"""Workflow module: suggest followups."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.followups import FOLLOWUPS_SYSTEM_PROMPT
from vlearn_ai.schemas import FollowUp, FollowUpSuggestions


async def run_suggest_followups(
    query: str,
    context: str,
    grounded_answer: str,
    model: BaseChatModel,
) -> FollowUpSuggestions:
    """Generate 2-3 relevant follow-up suggestions for deeper exploration."""
    prompt = (
        f"{FOLLOWUPS_SYSTEM_PROMPT}\n\n"
        f"<untrusted_course_context>\n{context}\n</untrusted_course_context>\n"
        f"Câu hỏi: {query}\n"
        f"Lời giải thích: {grounded_answer}\n"
    )

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(FollowUpSuggestions)
            res = await structured.ainvoke(prompt)
            if isinstance(res, FollowUpSuggestions) and len(res.followups) >= 1:
                return res
    except (AttributeError, ValueError, TypeError, RuntimeError):
        pass

    return FollowUpSuggestions(
        followups=[
            FollowUp(
                label="Hiểu cơ chế sâu hơn",
                question=f"Cơ chế chi tiết của '{query[:30]}' là gì?",
            ),
            FollowUp(
                label="Xem ví dụ thực tế",
                question="Cho thêm ví dụ ứng dụng thực tế của phần này.",
            ),
        ]
    )
