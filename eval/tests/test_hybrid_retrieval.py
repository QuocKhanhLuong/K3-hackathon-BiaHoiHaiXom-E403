"""Deterministic unit tests for local same-deck hybrid RAG behavior."""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.retrieval.embeddings import DeterministicFakeEmbeddingProvider
from backend.app.retrieval.local_slides import LocalSlideRepository


def _slide(page: int, title: str, body: str, deck: str = "d1") -> dict[str, object]:
    return {
        "deck_id": deck,
        "page": page,
        "page_in_deck": page,
        "title": title,
        "raw_text": body,
    }


def _repo(slides: list[dict[str, object]]) -> LocalSlideRepository:
    return LocalSlideRepository(
        slides=slides, semantic_provider=DeterministicFakeEmbeddingProvider()
    )


def _sources(context: str) -> list[str]:
    return re.findall(r'source_id="([^"]+)"', context)


def test_direct_body_definition_beats_title_only_and_neighbors():
    repo = _repo(
        [
            _slide(1, "LLM", "Agenda: LLM và Transformer."),
            _slide(6, "Đang xem", "Nội dung lân cận."),
            _slide(
                10,
                "Khái niệm",
                "LLM là Large Language Model, hay mô hình ngôn ngữ lớn.",
            ),
        ]
    )
    ranked = repo.retrieve(page_number=6, deck_id="d1", query="LLM là gì?")
    assert ranked.diagnostics.selected_source_order[0] == "d1-p10"
    assert ranked.chunks[0].intent_score == 1.0


def test_deictic_and_selected_text_prioritize_current_slide():
    repo = _repo(
        [
            _slide(5, "Khác", "Xa."),
            _slide(6, "Neo", "Đoạn chọn giải thích attention."),
            _slide(10, "Xa", "attention attention"),
        ]
    )
    ranked = repo.retrieve(
        page_number=6,
        deck_id="d1",
        query="đoạn này nghĩa là gì?",
        selected_text="attention",
    )
    assert ranked.diagnostics.query_mode == "deictic_contextual"
    assert ranked.diagnostics.selected_source_order[0] == "d1-p6"


def test_comparison_and_overview_query_modes_have_deterministic_order():
    repo = _repo(
        [
            _slide(1, "Agenda", "Nội dung: LLM, chatbot, Transformer."),
            _slide(2, "LLM", "LLM là mô hình ngôn ngữ lớn."),
            _slide(3, "Chatbot", "Chatbot là giao diện hội thoại."),
        ]
    )
    comparison = repo.retrieve(
        page_number=2, deck_id="d1", query="LLM và chatbot khác nhau thế nào?"
    )
    assert {"d1-p2", "d1-p3"}.issubset(comparison.diagnostics.selected_source_order)
    overview = repo.retrieve(
        page_number=3, deck_id="d1", query="Day 1 gồm những nội dung gì?"
    )
    assert overview.diagnostics.query_mode == "overview"
    assert overview.diagnostics.selected_source_order[0] == "d1-p1"


def test_invalid_deck_is_empty_and_never_crosses_decks():
    repo = _repo(
        [_slide(1, "D1", "LLM là mô hình."), _slide(1, "D2", "LLM là khác.", deck="d2")]
    )
    assert (
        repo.retrieve(page_number=1, deck_id="missing", query="LLM là gì?").chunks == []
    )
    assert _sources(
        repo.build_context(page_number=1, deck_id="d1", query="LLM là gì?")
    ) == ["d1-p1"]


def test_top_k_follows_reranking_and_bundle_budget_skips_long_low_priority_item():
    repo = _repo(
        [
            _slide(1, "Một", "vector"),
            _slide(2, "Hai", "vector vector"),
            _slide(3, "Ba", "vector vector vector"),
            _slide(8, "Neo", "không liên quan"),
        ]
    )
    context = repo.build_context(
        page_number=8, deck_id="d1", query="vector", max_slides=3
    )
    assert _sources(context) == ["d1-p8", "d1-p3", "d1-p2"]
    limited = repo.build_context(
        page_number=8, deck_id="d1", query="vector", max_chars=260, max_slides=3
    )
    assert "d1-p8" in limited


def test_semantic_failure_uses_lexical_results_without_downloading_model():
    class FailingProvider:
        name = "failing-test-provider"

        def embed_documents(self, texts):
            raise RuntimeError("offline")

        def embed_query(self, text):
            raise RuntimeError("offline")

    repo = LocalSlideRepository(
        slides=[_slide(1, "LLM", "LLM là mô hình ngôn ngữ lớn.")],
        semantic_provider=FailingProvider(),
    )
    result = repo.retrieve(page_number=1, deck_id="d1", query="LLM là gì?")
    assert result.chunks[0].lexical_score > 0
    assert result.diagnostics.semantic_fallback_reason == "RuntimeError"


def test_embedding_index_cache_is_reused(tmp_path: Path):
    class CountingProvider(DeterministicFakeEmbeddingProvider):
        name = "counting-fake"

        def __init__(self):
            super().__init__()
            self.document_calls = 0

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.document_calls += 1
            return super().embed_documents(texts)

    slides = [_slide(1, "LLM", "LLM là mô hình ngôn ngữ lớn.")]
    first_provider = CountingProvider()
    LocalSlideRepository(
        slides=slides, semantic_provider=first_provider, cache_dir=tmp_path
    ).retrieve(page_number=1, deck_id="d1", query="LLM là gì?")
    assert first_provider.document_calls == 1  # index build

    second_provider = CountingProvider()
    LocalSlideRepository(
        slides=slides, semantic_provider=second_provider, cache_dir=tmp_path
    ).retrieve(page_number=1, deck_id="d1", query="LLM là gì?")
    assert (
        second_provider.document_calls == 0
    )  # cached index; query embedding is separate
