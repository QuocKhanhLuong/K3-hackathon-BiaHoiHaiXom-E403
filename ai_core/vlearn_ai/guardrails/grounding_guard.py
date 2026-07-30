"""Grounding guard verifying citations against course context."""

import re

from vlearn_ai.schemas import Citation


def _normalize_text(text: str) -> str:
    """Normalize whitespace, case, and strip punctuation for deterministic matching."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def verify_grounding(
    answer: str,
    citations: list[Citation],
    context: str,
) -> tuple[bool, str | None]:
    """Verify that citations are valid, non-empty, unique, and present in context."""
    if not context or not context.strip():
        return False, "Course context is empty or missing."

    if not answer or not answer.strip():
        return False, "Answer is empty."

    norm_context = _normalize_text(context)

    # Empty citations when citations are required for grounded answers
    if not citations:
        return False, "Grounded answer contains no citations."

    citation_ids = [c.citation_id for c in citations]
    if len(citation_ids) != len(set(citation_ids)):
        return False, "Duplicate citation IDs found in answer."

    for citation in citations:
        snippet = citation.snippet.strip()
        if not snippet:
            return False, f"Citation '{citation.citation_id}' has an empty snippet."

        norm_snippet = _normalize_text(snippet)
        if norm_snippet in norm_context:
            continue

        # Word overlap ratio fallback
        snippet_words = set(norm_snippet.split())
        context_words = set(norm_context.split())
        if snippet_words and len(snippet_words & context_words) / len(snippet_words) >= 0.7:
            continue

        return False, f"Citation snippet '{snippet[:40]}...' is not grounded in context."

    return True, None
