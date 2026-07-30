"""Structured one-shot repair tool for invalid factual grounding output."""

from typing import Any

from langchain_core.language_models import BaseChatModel

from vlearn_ai.prompts.grounding_repair import GROUNDING_REPAIR_PROMPT
from vlearn_ai.prompts.messages import build_trusted_messages
from vlearn_ai.schemas import AIStructuredOutputError, GroundedAnswer


async def execute_repair_grounded_answer(
    *,
    candidate_answer: str | None,
    candidate_claims: list[dict[str, Any]],
    candidate_citations: list[dict[str, Any]],
    grounding_error: str | None,
    grounding_failure_type: str | None,
    grounding_invalid_citation_ids: list[str],
    grounding_uncovered_sentences: list[str],
    context: str,
    model: BaseChatModel,
) -> GroundedAnswer:
    """Repair only the candidate's grounded structure using the current context."""
    diagnostic = {
        "answer": candidate_answer or "",
        "claims": candidate_claims,
        "citations": candidate_citations,
        "grounding_error": grounding_error or "",
        "grounding_failure_type": grounding_failure_type or "",
        "invalid_citation_ids": grounding_invalid_citation_ids,
        "uncovered_sentences": grounding_uncovered_sentences,
    }
    untrusted_payload = (
        f"Course context:\n<untrusted_course_context>\n{context}\n</untrusted_course_context>\n\n"
        f"Candidate and diagnostics:\n<untrusted_candidate>\n{diagnostic}\n</untrusted_candidate>"
    )
    messages = build_trusted_messages(GROUNDING_REPAIR_PROMPT, untrusted_payload)
    try:
        if hasattr(model, "with_structured_output"):
            result = await model.with_structured_output(GroundedAnswer).ainvoke(messages)
            if isinstance(result, GroundedAnswer) and result.answer.strip():
                return result
    except Exception as exc:
        raise AIStructuredOutputError(
            f"repair_grounded_answer structured output failed: {exc}"
        ) from exc
    raise AIStructuredOutputError("repair_grounded_answer failed to produce GroundedAnswer.")
