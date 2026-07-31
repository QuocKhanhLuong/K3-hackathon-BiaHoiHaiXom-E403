"""Local, deterministic hybrid retrieval for one slide deck at a time."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from backend.app.retrieval.embeddings import (
    EmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
)
from backend.app.retrieval.models import (
    EvidenceChunk,
    RetrievalDiagnostics,
    RetrievalResult,
)
from backend.slide_loader import ALL_PDF_SLIDES

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = ROOT_DIR / "backend" / ".generated" / "vlearn_rag"
_TOKEN_RE = re.compile(r"[\wÀ-ỹ]+(?:[.%+\-=/][\wÀ-ỹ]+)*", re.UNICODE)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "các",
    "cái",
    "cho",
    "của",
    "có",
    "để",
    "gì",
    "is",
    "là",
    "một",
    "này",
    "những",
    "the",
    "thế",
    "trang",
    "và",
    "về",
    "với",
}


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(_normalize_text(value))
        if token not in _STOPWORDS and len(token) > 1
    ]


def _source_id(slide: dict[str, Any]) -> str:
    return str(
        slide.get("source_id")
        or f"{slide.get('deck_id', 'deck')}-p{slide.get('page_in_deck', slide.get('page', 1))}"
    )


def _body_text(slide: dict[str, Any]) -> str:
    """Keep title and body distinct even when PDF extraction repeats the title."""
    raw = str(slide.get("raw_text", "")).strip()
    title = str(slide.get("title", "")).strip()
    if title and _normalize_text(raw).startswith(_normalize_text(title)):
        return raw[len(title) :].lstrip().strip()
    return raw


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    denom = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return sum(x * y for x, y in zip(left, right)) / denom if denom else 0.0


class LocalSlideRepository:
    """A same-deck hybrid retrieval corpus backed only by local slide text.

    Independent factual queries use 0.45 semantic + 0.30 BM25 + 0.20 intent
    + 0.05 contextual score.  Deictic queries use 0.20 + 0.20 + 0.10 + 0.50.
    All scores are normalized to [0, 1] before deterministic reranking.
    """

    def __init__(
        self,
        slides: list[dict[str, Any]] | None = None,
        semantic_provider: EmbeddingProvider | None = None,
        cache_dir: Path | None = None,
        semantic_enabled: bool | None = None,
    ) -> None:
        self.slides = slides if slides is not None else ALL_PDF_SLIDES
        enabled_by_env = os.getenv("AI_RAG_SEMANTIC_ENABLED", "true").strip().lower()
        self.semantic_enabled = (
            semantic_enabled
            if semantic_enabled is not None
            else (
                semantic_provider is not None
                or enabled_by_env in {"1", "true", "yes", "on"}
            )
        )
        self.semantic_provider: EmbeddingProvider | None = (
            (
                semantic_provider
                or LocalSentenceTransformerEmbeddingProvider(
                    cache_dir=(cache_dir or DEFAULT_CACHE_DIR) / "models"
                )
            )
            if self.semantic_enabled
            else None
        )
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._embeddings: dict[str, list[float]] | None = None
        self._embedding_fingerprint: str | None = None
        self._semantic_fallback_reason: str | None = (
            None if self.semantic_enabled else "semantic_disabled"
        )
        self._index_load_build_ms = 0
        self._query_cache: dict[str, list[float]] = {}
        self._query_cache_limit = 64

    def list_slides(self, deck: str | None = None) -> list[dict[str, Any]]:
        if deck is not None:
            return [slide for slide in self.slides if slide.get("deck_id") == deck]
        return list(self.slides)

    def resolve(
        self, page_number: int | None, deck_id: str | None = None
    ) -> dict[str, Any] | None:
        target_slides = (
            self.list_slides(deck_id) if deck_id is not None else self.slides
        )
        if not target_slides:
            return None
        page = max(1, int(page_number or 1))
        return next(
            (
                slide
                for slide in target_slides
                if int(slide.get("page_in_deck", slide.get("page", -1))) == page
                or int(slide.get("page", -1)) == page
            ),
            target_slides[0],
        )

    def _chunks(self, deck_id: str) -> list[EvidenceChunk]:
        chunks: list[EvidenceChunk] = []
        seen_chunk_ids: set[str] = set()
        for slide in self.list_slides(deck_id):
            source = _source_id(slide)
            chunk_id = f"{source}-c1"
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)
            chunks.append(
                EvidenceChunk(
                    chunk_id=chunk_id,
                    source_id=source,
                    deck_id=deck_id,
                    page=int(slide.get("page", slide.get("page_in_deck", 1))),
                    page_in_deck=int(slide.get("page_in_deck", slide.get("page", 1))),
                    title=str(slide.get("title", "")).strip(),
                    text=_body_text(slide),
                )
            )
        return chunks

    @staticmethod
    def _query_mode(query: str, selected_text: str) -> str:
        q = _normalize_text(query)
        if re.search(r"\b(?:slide|slides|trang)\s+\d+", q):
            return "explicit_page"
        if selected_text.strip() or any(
            phrase in q
            for phrase in ("đoạn này", "slide này", "cái này", "này nghĩa là gì")
        ):
            return "deictic_contextual"
        if any(
            term in q
            for term in ("khác nhau", "so sánh", "so sanh", " so với ", " vs ")
        ):
            return "comparison"
        if any(
            term in q
            for term in (
                "gồm những",
                "noi dung gi",
                "nội dung gì",
                "tổng quan",
                "overview",
            )
        ):
            return "overview"
        return "independent_factual"

    @staticmethod
    def _explicit_pages(query: str) -> set[int]:
        pages: set[int] = set()
        for match in re.finditer(
            r"\b(?:slide|slides|trang)\s+(\d+)(?:\s*(?:đến|to|[-–])\s*(\d+))?",
            _normalize_text(query),
        ):
            start, end = int(match.group(1)), int(match.group(2) or match.group(1))
            pages.update(range(min(start, end), max(start, end) + 1))
        return pages

    @staticmethod
    def _definition_entity(query: str) -> str | None:
        match = re.search(
            r"^\s*(.{1,80}?)\s+(?:là|la)\s+gì\s*[?？]?$", query, re.IGNORECASE
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _bm25_scores(chunks: list[EvidenceChunk], query: str) -> list[float]:
        query_terms = _tokens(query)
        if not query_terms or not chunks:
            return [0.0] * len(chunks)
        documents = [_tokens(f"{chunk.title} {chunk.text}") for chunk in chunks]
        lengths = [len(doc) or 1 for doc in documents]
        average_length = sum(lengths) / len(lengths)
        document_frequency = Counter(term for doc in documents for term in set(doc))
        k1, b = 1.2, 0.75
        raw: list[float] = []
        for doc, length in zip(documents, lengths):
            frequencies = Counter(doc)
            score = 0.0
            for term in query_terms:
                freq = frequencies[term]
                if not freq:
                    continue
                idf = math.log(
                    1
                    + (len(documents) - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                score += (
                    idf
                    * (freq * (k1 + 1))
                    / (freq + k1 * (1 - b + b * length / average_length))
                )
            raw.append(score)
        maximum = max(raw, default=0.0)
        return [score / maximum if maximum else 0.0 for score in raw]

    def _intent_score(
        self, chunk: EvidenceChunk, query: str, mode: str, explicit_pages: set[int]
    ) -> float:
        title = _normalize_text(chunk.title)
        body = _normalize_text(chunk.text)
        query_tokens = set(_tokens(query))
        entity = self._definition_entity(query)
        if mode == "explicit_page":
            return 1.0 if chunk.page_in_deck in explicit_pages else 0.0
        if mode == "overview":
            return (
                1.0
                if any(
                    word in title or word in body
                    for word in (
                        "agenda",
                        "mục lục",
                        "nội dung",
                        "tổng quan",
                        "summary",
                        "outline",
                    )
                )
                else 0.0
            )
        if entity:
            entity_normalized = _normalize_text(entity)
            escaped = re.escape(entity_normalized)
            direct_patterns = (
                rf"\b{escaped}\s+(?:là|la|=)\s*(?!gì\b)",
                rf"\b{escaped}\s+(?:viết tắt|viet tat)\s+của",
            )
            if re.search(rf"\b{escaped}\s*\(", body) or re.search(
                rf"\b{escaped}\s+(?:là|la)\s+(?:một|mot|a|an|large|mô hình|mo hinh)",
                body,
            ):
                return 1.0
            if any(re.search(pattern, body) for pattern in direct_patterns):
                return 0.85
            if entity_normalized in body:
                return 0.65
            if entity_normalized in title:
                return 0.10
            return 0.0
        body_overlap = len(query_tokens.intersection(_tokens(chunk.text)))
        title_overlap = len(query_tokens.intersection(_tokens(chunk.title)))
        return min(1.0, 0.15 * body_overlap + 0.03 * title_overlap)

    def _context_score(
        self, chunk: EvidenceChunk, current_page: int, mode: str, selected_text: str
    ) -> float:
        distance = abs(chunk.page_in_deck - current_page)
        nearby = max(0.0, 1.0 - distance / 4.0)
        if mode == "deictic_contextual":
            selected_overlap = set(_tokens(selected_text)).intersection(
                _tokens(chunk.text)
            )
            return (
                max(nearby, 1.0 if selected_overlap else 0.0)
                if chunk.page_in_deck == current_page
                else nearby * 0.55
            )
        if mode == "explicit_page":
            return 0.0
        return nearby if chunk.page_in_deck == current_page else nearby * 0.25

    def _embedding_cache_path(self, chunks: list[EvidenceChunk]) -> Path:
        provider_name = getattr(
            self.semantic_provider, "name", type(self.semantic_provider).__name__
        )
        payload = "\n".join(
            f"{chunk.chunk_id}\x00{chunk.title}\x00{chunk.text}" for chunk in chunks
        )
        fingerprint = hashlib.sha256(f"{provider_name}\n{payload}".encode()).hexdigest()
        self._embedding_fingerprint = fingerprint
        return self.cache_dir / f"{fingerprint}.json"

    def _document_embeddings(
        self, chunks: list[EvidenceChunk]
    ) -> dict[str, list[float]] | None:
        if not self.semantic_enabled or self.semantic_provider is None:
            self._semantic_fallback_reason = "semantic_disabled"
            return None
        if self._embeddings is not None:
            return self._embeddings
        started = time.perf_counter()
        path = self._embedding_cache_path(chunks)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                embeddings = data.get("embeddings", {})
                if set(embeddings) == {chunk.chunk_id for chunk in chunks}:
                    self._embeddings = {
                        key: list(map(float, value))
                        for key, value in embeddings.items()
                    }
                    return self._embeddings
            vectors = self.semantic_provider.embed_documents(
                [f"{chunk.title}\n{chunk.text}" for chunk in chunks]
            )
            if len(vectors) != len(chunks):
                raise ValueError("embedding provider returned wrong document count")
            self._embeddings = {
                chunk.chunk_id: vector for chunk, vector in zip(chunks, vectors)
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"embeddings": self._embeddings}), encoding="utf-8"
            )
            return self._embeddings
        except Exception as exc:  # noqa: BLE001 - optional local provider must not break retrieval
            self._semantic_fallback_reason = type(exc).__name__
            self._embeddings = None
            return None
        finally:
            self._index_load_build_ms = int((time.perf_counter() - started) * 1000)

    def _semantic_scores(
        self, chunks: list[EvidenceChunk], query: str
    ) -> tuple[list[float], int]:
        started = time.perf_counter()
        if not self.semantic_enabled or self.semantic_provider is None:
            self._semantic_fallback_reason = "semantic_disabled"
            return [0.0] * len(chunks), int((time.perf_counter() - started) * 1000)
        embeddings = self._document_embeddings(chunks)
        if embeddings is None:
            return [0.0] * len(chunks), int((time.perf_counter() - started) * 1000)
        try:
            query_vector = self._query_cache.get(query)
            if query_vector is None:
                query_vector = self.semantic_provider.embed_query(query)
                if len(self._query_cache) >= self._query_cache_limit:
                    self._query_cache.pop(next(iter(self._query_cache)))
                self._query_cache[query] = query_vector
            raw = [
                max(0.0, _cosine(query_vector, embeddings[chunk.chunk_id]))
                for chunk in chunks
            ]
            maximum = max(raw, default=0.0)
            return (
                [score / maximum if maximum else 0.0 for score in raw],
                int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - lexical fallback is intentional
            self._semantic_fallback_reason = type(exc).__name__
            return [0.0] * len(chunks), int((time.perf_counter() - started) * 1000)

    def retrieve(
        self,
        *,
        page_number: int,
        deck_id: str,
        query: str,
        selected_text: str = "",
        top_k: int = 5,
    ) -> RetrievalResult:
        """Return deterministic, same-deck ranked evidence; never cross-deck."""
        current = self.resolve(page_number, deck_id)
        chunks = self._chunks(deck_id)
        if not chunks or current is None:
            diagnostics = RetrievalDiagnostics(
                query_mode="invalid_deck",
                selected_source_order=[],
                candidate_count=0,
                selected_count=0,
                lexical_latency_ms=0,
                semantic_latency_ms=0,
                reranking_latency_ms=0,
                semantic_fallback_reason="invalid_deck",
            )
            return RetrievalResult(chunks=[], diagnostics=diagnostics)

        mode = self._query_mode(query, selected_text)
        explicit_pages = self._explicit_pages(query)
        lex_started = time.perf_counter()
        lexical = self._bm25_scores(chunks, f"{query} {selected_text}".strip())
        lexical_ms = int((time.perf_counter() - lex_started) * 1000)
        semantic, semantic_ms = self._semantic_scores(chunks, query)
        rerank_started = time.perf_counter()
        current_page = int(current.get("page_in_deck", page_number))
        weights = (
            (0.20, 0.20, 0.10, 0.50)
            if mode == "deictic_contextual"
            else (0.45, 0.30, 0.20, 0.05)
        )
        ranked: list[EvidenceChunk] = []
        for chunk, lexical_score, semantic_score in zip(chunks, lexical, semantic):
            intent_score = self._intent_score(chunk, query, mode, explicit_pages)
            context_score = self._context_score(
                chunk, current_page, mode, selected_text
            )
            final_score = (
                weights[0] * semantic_score
                + weights[1] * lexical_score
                + weights[2] * intent_score
                + weights[3] * context_score
            )
            # An explicit page is a user navigation request, not a weak hint.
            if mode == "explicit_page" and chunk.page_in_deck in explicit_pages:
                final_score += 1.0
            methods = ["lexical"] if lexical_score else []
            if semantic_score:
                methods.append("semantic")
            if intent_score:
                methods.append("intent")
            if context_score:
                methods.append("context")
            ranked.append(
                EvidenceChunk(
                    **{
                        **chunk.diagnostic_dict(),
                        "lexical_score": lexical_score,
                        "semantic_score": semantic_score,
                        "intent_score": intent_score,
                        "context_score": context_score,
                        "final_score": final_score,
                        "retrieval_methods": methods,
                    }
                )
            )
        ranked.sort(
            key=lambda item: (
                -item.final_score,
                -item.intent_score,
                item.page_in_deck,
                item.source_id,
            )
        )
        best_by_source: dict[str, EvidenceChunk] = {}
        for chunk in ranked:
            best_by_source.setdefault(chunk.source_id, chunk)
        selected = list(best_by_source.values())[: max(0, top_k)]
        rerank_ms = int((time.perf_counter() - rerank_started) * 1000)
        diagnostics = RetrievalDiagnostics(
            query_mode=mode,
            selected_source_order=[chunk.source_id for chunk in selected],
            candidate_count=len(chunks),
            selected_count=len(selected),
            lexical_latency_ms=lexical_ms,
            semantic_latency_ms=semantic_ms,
            reranking_latency_ms=rerank_ms,
            index_load_build_ms=self._index_load_build_ms,
            semantic_fallback_reason=self._semantic_fallback_reason,
        )
        return RetrievalResult(chunks=selected, diagnostics=diagnostics)

    def build_context(
        self,
        page_number: int,
        deck_id: str | None = None,
        selected_text: str = "",
        query: str = "",
        recent_history: list[dict[str, Any]] | None = None,
        max_chars: int = 12000,
        max_slides: int = 5,
    ) -> str:
        """Render a focused evidence bundle, preserving retrieval order.

        The current slide remains an anchor for compatibility when it fits the
        requested factual bundle, but explicit-page queries always lead with the
        explicitly requested evidence.  The full deck remains the corpus.
        """
        started = time.perf_counter()
        if deck_id is None:
            current = self.resolve(page_number)
            deck_id = str(current.get("deck_id")) if current else None
        if not deck_id or not self.list_slides(deck_id):
            return "=== KHÓA HỌC: không tìm thấy deck được yêu cầu ==="
        history_text = " ".join(
            str(item.get("content", ""))
            for item in (recent_history or [])[-2:]
            if isinstance(item, dict)
        )
        result = self.retrieve(
            page_number=page_number,
            deck_id=deck_id,
            query=f"{query} {history_text}".strip(),
            selected_text=selected_text,
            top_k=max_slides,
        )
        chunks = list(result.chunks)
        current = self.resolve(page_number, deck_id)
        current_source = _source_id(current) if current else None
        if result.diagnostics.query_mode != "explicit_page" and current_source:
            current_chunk = next(
                (chunk for chunk in chunks if chunk.source_id == current_source), None
            )
            if current_chunk is None:
                current_chunk = next(
                    (
                        chunk
                        for chunk in self._chunks(deck_id)
                        if chunk.source_id == current_source
                    ),
                    None,
                )
                if current_chunk is not None:
                    chunks = [current_chunk, *chunks[: max(0, max_slides - 1)]]
            if current_chunk:
                chunks.remove(current_chunk)
                chunks.insert(0, current_chunk)
        deck_name = str((current or {}).get("deck_name", "Bài học"))
        pieces = [
            f"=== KHÓA HỌC: {deck_name} (Tổng số slide: {len(self.list_slides(deck_id))}) ==="
        ]
        if selected_text.strip():
            pieces.append(
                f"=== ĐOẠN HỌC VIÊN ĐÃ CHỌN (ƯU TIÊN CAO NHẤT) ===\n{selected_text.strip()}"
            )
        used_sources: set[str] = set()
        for chunk in chunks:
            if chunk.source_id in used_sources:
                continue
            piece = (
                f'[source source_id="{chunk.source_id}" chunk_id="{chunk.chunk_id}" '
                f"page={chunk.page} deck={chunk.deck_id} page_in_deck={chunk.page_in_deck}]\n"
                f"Tiêu đề: {chunk.title}\n{chunk.text}"
            )
            used = sum(len(part) for part in pieces) + 2 * len(pieces)
            if used + len(piece) > max_chars:
                continue
            pieces.append(piece)
            used_sources.add(chunk.source_id)
        # The result is available for callers needing safe, non-vector diagnostics.
        self.last_retrieval_diagnostics = RetrievalDiagnostics(
            **{
                **result.diagnostics.__dict__,
                "context_build_latency_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        return "\n\n".join(pieces)

    def pdf_path_for_page(
        self, page_number: int, deck_id: str | None = None
    ) -> tuple[Path, int] | None:
        slide = self.resolve(page_number, deck_id=deck_id)
        code = str((slide or {}).get("code", ""))
        if "#page=" not in code:
            return None
        filename, page_text = code.split("#page=", 1)
        pdf_path = (
            ROOT_DIR / "data" / "vlearn-pack" / "slides" / Path(filename).name
        ).resolve()
        slides_dir = (ROOT_DIR / "data" / "vlearn-pack" / "slides").resolve()
        return (
            (pdf_path, int(page_text) - 1) if slides_dir in pdf_path.parents else None
        )
