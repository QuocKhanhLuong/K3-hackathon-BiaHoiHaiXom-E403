"""Source-scoped grounding validation for structured course answers."""

from __future__ import annotations

import html
import re
import unicodedata

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


_HEADER_RE = re.compile(
    r'^\[source\s+source_id="([^"\[\]]+)"(?:\s+[^\]]*)?\]\s*$', re.MULTILINE
)
_CANONICAL_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "−": "-",
    }
)
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
_NEGATION_RE = re.compile(
    r"(?<!\\w)(?:không\\s+phải|khong\\s+phai|không|khong|chẳng|chua|chưa|"
    r"not|no|never|without)(?!\\w)",
    re.IGNORECASE,
)


def _source_texts(context: str) -> dict[str, list[str]]:
    """Parse each source header and retain only text from that exact source."""
    matches = list(_HEADER_RE.finditer(context))
    sources: dict[str, list[str]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(context)
        source_id = match.group(1)
        sources.setdefault(source_id, []).append(context[match.end() : end].strip())
    return sources


def _context_source_ids(context: str) -> set[str]:
    """Extract source IDs only from syntactically valid source headers."""
    return set(_source_texts(context))


def _canonicalize(text: str) -> str:
    """Normalize Unicode/HTML/whitespace without erasing factual punctuation."""
    normalized = html.unescape(unicodedata.normalize("NFKC", text)).translate(
        _CANONICAL_TRANSLATION
    )
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _content_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[\wÀ-ỹ]+(?:[.%+\-=/][\wÀ-ỹ]+)*", _canonicalize(text))
    return [token for token in tokens if token not in _STOPWORDS and len(token) > 1]


def _protected_facts(text: str) -> set[str]:
    """Facts that must never be lost to token-overlap permissiveness."""
    canonical = _canonicalize(text)
    values = set(re.findall(r"(?<!\w)-?\d+(?:\.\d+)?%?", canonical))
    values.update(re.findall(r"(?:<=|>=|!=|==|=|\+|/|\*)", canonical))
    if _NEGATION_RE.search(canonical):
        values.add("__negation__")
    return values


def _has_negation(text: str) -> bool:
    """Return the polarity marker without deleting it from lexical comparison."""
    return bool(_NEGATION_RE.search(_canonicalize(text)))


def _claim_supported_by_citation(claim: str, snippet: str) -> bool:
    claim_normalized = _canonicalize(claim)
    snippet_normalized = _canonicalize(snippet)
    # Token overlap cannot establish an opposite claim.  Check polarity before
    # accepting a substring or high-overlap match, while preserving all factual
    # punctuation and numeric values in the normal comparison below.
    if _has_negation(claim_normalized) != _has_negation(snippet_normalized):
        return False
    if claim_normalized in snippet_normalized or snippet_normalized in claim_normalized:
        return True
    claim_facts = _protected_facts(claim)
    snippet_facts = _protected_facts(snippet)
    if not claim_facts.issubset(snippet_facts):
        return False
    claim_tokens = set(_content_tokens(claim))
    snippet_tokens = set(_content_tokens(snippet))
    if not claim_tokens or not snippet_tokens:
        return False
    overlap = claim_tokens & snippet_tokens
    return len(overlap) / max(len(claim_tokens), 1) >= 0.7


def _answer_sentences(answer: str) -> list[str]:
    """Return every factual-looking answer sentence; no keyword/tag bypasses."""
    return [
        sentence.strip()
        for sentence in re.split(r"[.!?]\s+|\n+", answer)
        if sentence.strip()
    ]


def validate_grounding(
    answer: str,
    citations: list[Citation],
    context: str,
    claims: list[GroundedClaim] | None = None,
) -> GroundingResult:
    """Verify citations and claims against the particular cited source text."""
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

    citation_ids = [citation.citation_id for citation in citations]
    if len(citation_ids) != len(set(citation_ids)):
        return GroundingResult(
            valid=False,
            error="Duplicate citation IDs found in answer.",
            failure_type="duplicate_citation_ids",
        )
    source_texts = _source_texts(context)
    for citation in citations:
        if citation.citation_id not in source_texts:
            return GroundingResult(
                valid=False,
                error=f"Citation ID '{citation.citation_id}' does not exist in the current course context.",
                failure_type="invalid_citation_id",
                invalid_citation_ids=[citation.citation_id],
            )
        snippet = citation.snippet.strip()
        if not snippet:
            return GroundingResult(
                valid=False,
                error=f"Citation '{citation.citation_id}' has an empty snippet.",
                failure_type="empty_citation_snippet",
            )
        canonical_snippet = _canonicalize(snippet)
        if not any(
            canonical_snippet in _canonicalize(text)
            for text in source_texts[citation.citation_id]
        ):
            return GroundingResult(
                valid=False,
                error=f"Citation snippet '{snippet[:40]}...' is not grounded in source '{citation.citation_id}'.",
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
        if any(
            citation_id not in valid_citation_ids
            for citation_id in claim_obj.citation_ids
        ):
            unknown = next(
                citation_id
                for citation_id in claim_obj.citation_ids
                if citation_id not in valid_citation_ids
            )
            return GroundingResult(
                valid=False,
                error=f"Claim references unknown citation ID '{unknown}'.",
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
            _claim_supported_by_citation(sentence, claim_text)
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
