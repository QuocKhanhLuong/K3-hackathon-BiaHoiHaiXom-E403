"""Grounding guard verifying citations and claims against course context."""

import re

from vlearn_ai.schemas import Citation, GroundedClaim


def _normalize_text(text: str) -> str:
    """Deterministic whitespace and case normalization."""
    return re.sub(r"\s+", " ", text.strip().lower())


_STOPWORDS = {
    "va",
    "và",
    "la",
    "là",
    "cua",
    "của",
    "voi",
    "với",
    "de",
    "để",
    "mot",
    "một",
    "trong",
    "cho",
    "cac",
    "các",
    "the",
    "mà",
    "as",
    "is",
    "a",
    "an",
}


def _content_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[\wÀ-ỹ]+", text.lower())
    return [token for token in tokens if token not in _STOPWORDS and len(token) > 1]


def _claim_supported_by_citation(claim: str, snippet: str) -> bool:
    claim_norm = _normalize_text(claim)
    snippet_norm = _normalize_text(snippet)
    if claim_norm in snippet_norm or snippet_norm in claim_norm:
        return True
    claim_tokens = set(_content_tokens(claim))
    snippet_tokens = set(_content_tokens(snippet))
    if not claim_tokens or not snippet_tokens:
        return False
    if claim_tokens <= snippet_tokens or snippet_tokens <= claim_tokens:
        return True
    overlap = claim_tokens & snippet_tokens
    return len(overlap) / max(min(len(claim_tokens), len(snippet_tokens)), 1) >= 0.4


def verify_grounding(
    answer: str,
    citations: list[Citation],
    context: str,
    claims: list[GroundedClaim] | None = None,
) -> tuple[bool, str | None]:
    """Strictly verify that citations and claims are valid, non-empty, unique, present in context, and cover the answer."""
    if not context or not context.strip():
        return False, "Course context is empty or missing."

    if not answer or not answer.strip():
        return False, "Answer is empty."

    norm_context = _normalize_text(context)

    # Empty citations fail for grounded answers UNLESS answer contains 0 claims (conversational/de-escalation)
    if not citations:
        if not claims:
            return True, None
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

    if not claims:
        return False, "Grounded answer contains no structured claims."

    # Validate structured claims and claim-to-citation support.
    citation_by_id = {citation.citation_id: citation for citation in citations}
    for claim_obj in claims:
        if not claim_obj.claim.strip():
            return False, "Grounded claim text is empty."
        if not claim_obj.citation_ids:
            return (
                False,
                f"Claim '{claim_obj.claim[:30]}' does not reference any citation ID.",
            )

        supporting_citations: list[Citation] = []
        for cid in claim_obj.citation_ids:
            if cid not in valid_citation_ids:
                return False, f"Claim references unknown citation ID '{cid}'."
            supporting_citations.append(citation_by_id[cid])

        claim_supported = False
        for citation in supporting_citations:
            if _claim_supported_by_citation(claim_obj.claim, citation.snippet):
                claim_supported = True
                break

        if not claim_supported:
            return (
                False,
                f"Claim '{claim_obj.claim[:40]}' is not supported by its cited evidence.",
            )

    # Answer sentence coverage check
    clean_ans = answer
    for prefix in ["Ví dụ:", "Lời động viên:", "Gợi ý:"]:
        if prefix in clean_ans:
            clean_ans = clean_ans.split(prefix)[0]

    sentences = [s.strip() for s in re.split(r"[.!?]\s+|\n+", clean_ans) if s.strip()]
    claim_texts = [cl.claim for cl in claims]

    for sentence in sentences:
        s_tokens = set(_content_tokens(sentence))
        if len(s_tokens) < 3:
            continue
        covered = False
        for c_text in claim_texts:
            c_tokens = set(_content_tokens(c_text))
            if (
                s_tokens <= c_tokens
                or c_tokens <= s_tokens
                or (len(s_tokens & c_tokens) / max(len(s_tokens), 1) >= 0.7)
            ):
                covered = True
                break
        if not covered:
            return (
                False,
                f"Factual sentence '{sentence[:40]}...' is not covered by any grounded claim.",
            )

    return True, None
