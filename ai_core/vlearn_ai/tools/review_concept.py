"""Pedagogical tool 1: review_concept."""

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.pedagogical_tools import REVIEW_CONCEPT_PROMPT
from vlearn_ai.schemas import Citation, GroundedAnswer


async def execute_review_concept(
    query: str,
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Explain an important concept using only the supplied course context."""
    prompt = REVIEW_CONCEPT_PROMPT.format(
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

    # Fallback/default structure for testing or raw model response
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
