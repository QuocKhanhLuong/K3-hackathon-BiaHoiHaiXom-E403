"""Grounding guard verifying citations and claims against course context."""

import re

from vlearn_ai.schemas import Citation, GroundedClaim


def _normalize_text(text: str) -> str:
    """Deterministic whitespace and case normalization."""
    return re.sub(r"\s+", " ", text.strip().lower())


def verify_grounding(
    answer: str,
    citations: list[Citation],
    context: str,
    claims: list[GroundedClaim] | None = None,
) -> tuple[bool, str | None]:
    """Strictly verify that citations and claims are valid, non-empty, unique, and present in context."""
    if not context or not context.strip():
        return False, "Course context is empty or missing."

    if not answer or not answer.strip():
        return False, "Answer is empty."

    norm_context = _normalize_text(context)

    # Empty citations fail for grounded answers
    if not citations:
        return False, "Grounded answer contains no citations."

    citation_ids = [c.citation_id for c in citations]
    if len(citation_ids) != len(set(citation_ids)):
        return False, "Duplicate citation IDs found in answer."

    valid_citation_ids = set(citation_ids)

    for citation in citations:
        snippet = citation.snippet.strip()
        if not snippet:
            return False, f"Citation '{citation.citation_id}' has an empty snippet."

        norm_snippet = _normalize_text(snippet)
        # Check strict substring match in normalized course context
        if norm_snippet not in norm_context:
            return (
                False,
                f"Citation snippet '{snippet[:40]}...' is not grounded in context.",
            )

    # Validate structured claims if provided
    if claims:
        for claim_obj in claims:
            if not claim_obj.citation_ids:
                return (
                    False,
                    f"Claim '{claim_obj.claim[:30]}' does not reference any citation ID.",
                )

            for cid in claim_obj.citation_ids:
                if cid not in valid_citation_ids:
                    return False, f"Claim references unknown citation ID '{cid}'."

    return True, None
