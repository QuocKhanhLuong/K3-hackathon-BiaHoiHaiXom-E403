"""Grounding guard verifying citations and claims against course context."""

import re

from pydantic import BaseModel, Field

from vlearn_ai.schemas import Citation, GroundedClaim


class GroundingResult(BaseModel):
    """Internal structured outcome for grounding verification diagnostics."""

    valid: bool
    error: str | None = None
    failure_type: str | None = None
    invalid_citation_ids: list[str] = Field(default_factory=list)
    uncovered_sentences: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


def _context_source_ids(context: str) -> set[str]:
    """Extract source IDs only from valid course-context source headers."""
    return set(
        re.findall(r'\[source\s+source_id="([^"\[\]]+)"(?:\s+[^\]]*)?\]', context)
    )


def _normalize_text(text: str) -> str:
    """Deterministic whitespace and case normalization."""
    return re.sub(r"\s+", " ", text.strip().lower())

def _normalize_for_match(text: str) -> str:
    """Aggressive normalization removing punctuation for robust substring matching."""
    text = text.lower()
    text = re.sub(r'[^\w\sÀ-ỹ]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


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


def _answer_sentences(answer: str) -> list[str]:
    """Return factual answer sentences subject to claim-coverage validation."""
    clean_answer = answer
    for prefix in ["Ví dụ:", "Lời động viên:", "Gợi ý:"]:
        if prefix in clean_answer:
            clean_answer = clean_answer.split(prefix)[0]
    return [s.strip() for s in re.split(r"[.!?]\s+|\n+", clean_answer) if s.strip()]


def validate_grounding(
    answer: str,
    citations: list[Citation],
    context: str,
    claims: list[GroundedClaim] | None = None,
) -> GroundingResult:
    """Return detailed validation of a factual structured grounded answer."""
    if not context or not context.strip():
        return GroundingResult(
            valid=False,
            error="Course context is empty or missing.",
            failure_type="empty_context",
        )
    if not answer or not answer.strip():
        return GroundingResult(
            valid=False, error="Answer is empty.", failure_type="empty_answer"
        )
    if not citations:
        return GroundingResult(
            valid=False,
            error="Grounded answer contains no citations.",
            failure_type="missing_citations",
        )
    if not claims:
        return GroundingResult(
            valid=False,
            error="Grounded answer contains no structured claims.",
            failure_type="missing_claims",
        )

    citation_ids = [c.citation_id for c in citations]
    if len(citation_ids) != len(set(citation_ids)):
        return GroundingResult(
            valid=False,
            error="Duplicate citation IDs found in answer.",
            failure_type="duplicate_citation_ids",
        )

    context_source_ids = _context_source_ids(context)
    for citation in citations:
        if citation.citation_id not in context_source_ids:
            return GroundingResult(
                valid=False,
                error=f"Citation ID '{citation.citation_id}' does not exist in the current course context.",
                failure_type="invalid_citation_id",
                invalid_citation_ids=[citation.citation_id],
            )

    norm_context = _normalize_for_match(context)
    for citation in citations:
        snippet = citation.snippet.strip()
        if not snippet:
            return GroundingResult(
                valid=False,
                error=f"Citation '{citation.citation_id}' has an empty snippet.",
                failure_type="empty_citation_snippet",
            )
        if _normalize_for_match(snippet) not in norm_context:
            return GroundingResult(
                valid=False,
                error=f"Citation snippet '{snippet[:40]}...' is not grounded in context.",
                failure_type="citation_snippet_not_in_context",
            )

    valid_citation_ids = set(citation_ids)
    citation_by_id = {citation.citation_id: citation for citation in citations}
    for claim_obj in claims:
        if not claim_obj.claim.strip():
            return GroundingResult(
                valid=False,
                error="Grounded claim text is empty.",
                failure_type="empty_claim",
            )
        if not claim_obj.citation_ids:
            return GroundingResult(
                valid=False,
                error=f"Claim '{claim_obj.claim[:30]}' does not reference any citation ID.",
                failure_type="missing_claim_citation",
            )
        for citation_id in claim_obj.citation_ids:
            if citation_id not in valid_citation_ids:
                return GroundingResult(
                    valid=False,
                    error=f"Claim references unknown citation ID '{citation_id}'.",
                    failure_type="unknown_claim_citation",
                )
        if not any(
            _claim_supported_by_citation(
                claim_obj.claim, citation_by_id[citation_id].snippet
            )
            for citation_id in claim_obj.citation_ids
        ):
            return GroundingResult(
                valid=False,
                error=f"Claim '{claim_obj.claim[:40]}' is not supported by its cited evidence.",
                failure_type="unsupported_claim",
                unsupported_claims=[claim_obj.claim],
            )

    claim_texts = [claim.claim for claim in claims]
    for sentence in _answer_sentences(answer):
        sentence_tokens = set(_content_tokens(sentence))
        if len(sentence_tokens) < 3:
            continue
        if not any(
            sentence_tokens <= set(_content_tokens(claim_text))
            or set(_content_tokens(claim_text)) <= sentence_tokens
            or len(sentence_tokens & set(_content_tokens(claim_text)))
            / max(len(sentence_tokens), 1)
            >= 0.7
            for claim_text in claim_texts
        ):
            return GroundingResult(
                valid=False,
                error=f"Factual sentence '{sentence[:40]}...' is not covered by any grounded claim.",
                failure_type="uncovered_factual_sentence",
                uncovered_sentences=[sentence],
            )
    return GroundingResult(valid=True)


def verify_grounding(
    answer: str,
    citations: list[Citation],
    context: str,
    claims: list[GroundedClaim] | None = None,
) -> tuple[bool, str | None]:
    """Backwards-compatible tuple interface for grounding verification."""
    result = validate_grounding(answer, citations, context, claims)
    return result.valid, result.error
