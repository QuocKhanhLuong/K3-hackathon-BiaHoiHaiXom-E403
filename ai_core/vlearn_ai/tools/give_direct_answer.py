"""Pedagogical tool 2: give_direct_answer."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.pedagogical_tools import GIVE_DIRECT_ANSWER_PROMPT
from vlearn_ai.schemas import Citation, GroundedAnswer


async def execute_give_direct_answer(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Answer a simple factual question directly and concisely."""
    prompt = GIVE_DIRECT_ANSWER_PROMPT.format(
        selected_context=context,
        user_query=query,
    )

    try:
        if hasattr(model, "with_structured_output"):
            structured = model.with_structured_output(GroundedAnswer)
            res = await structured.ainvoke(prompt)
            if isinstance(res, GroundedAnswer):
                return res
    except (AttributeError, ValueError, TypeError, RuntimeError):
        pass

    res_text = (
        (await model.ainvoke(prompt)).content
        if hasattr(model, "ainvoke")
        else str(model)
    )

    return GroundedAnswer(
        answer=str(res_text),
        evidence=[context[:100]] if context else [],
        citations=[Citation(citation_id="ctx_1", snippet=context[:100])]
        if context
        else [],
    )
