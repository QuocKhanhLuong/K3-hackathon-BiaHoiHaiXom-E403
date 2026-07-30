"""Typed internal models for the local slide retrieval pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class EvidenceChunk:
    """A retrievable unit of course evidence.

    A chunk currently represents one slide.  Keeping ``chunk_id`` separate
    from ``source_id`` lets a future multi-chunk slide retain the existing
    product citation format.
    """

    chunk_id: str
    source_id: str
    deck_id: str
    page: int
    page_in_deck: int
    title: str
    text: str
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    intent_score: float = 0.0
    context_score: float = 0.0
    final_score: float = 0.0
    retrieval_methods: list[str] = field(default_factory=list)

    def diagnostic_dict(self) -> dict[str, object]:
        """Return safe retrieval diagnostics without vector values."""
        return asdict(self)


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """Safe observability data for a retrieval request."""

    query_mode: str
    selected_source_order: list[str]
    candidate_count: int
    selected_count: int
    lexical_latency_ms: int
    semantic_latency_ms: int
    reranking_latency_ms: int
    context_build_latency_ms: int = 0
    index_load_build_ms: int = 0
    semantic_fallback_reason: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    """Ranked same-deck evidence plus query-level diagnostics."""

    chunks: list[EvidenceChunk]
    diagnostics: RetrievalDiagnostics
