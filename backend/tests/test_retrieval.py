"""Unit tests for backend multi-slide retrieval and citation mapping."""

from backend.app.ai.result_mapper import _page_from_citation
from backend.app.retrieval.local_slides import LocalSlideRepository


def test_retrieval_current_slide_always_kept():
    repo = LocalSlideRepository()
    ctx = repo.build_context(page_number=5)
    assert "[source" in ctx
    assert "page=5" in ctx


def test_retrieval_neighboring_slides_retrieved():
    repo = LocalSlideRepository()
    # page 5 should include neighbors ±2 (e.g. pages 3, 4, 5, 6, 7)
    ctx = repo.build_context(page_number=5)
    assert "page=5" in ctx
    assert "page=3" in ctx or "page=4" in ctx or "page=6" in ctx or "page=7" in ctx


def test_retrieval_related_slide_in_same_deck_retrieved():
    repo = LocalSlideRepository()
    ctx = repo.build_context(page_number=1, query="Attention mechanism Transformer")
    assert "[source" in ctx
    assert "KHÓA HỌC:" in ctx


def test_retrieval_no_cross_deck():
    mock_slides = [
        {
            "page": 1,
            "deck_id": "d1",
            "page_in_deck": 1,
            "title": "Slide 1",
            "raw_text": "Content 1",
        },
        {
            "page": 2,
            "deck_id": "d1",
            "page_in_deck": 2,
            "title": "Slide 2",
            "raw_text": "Content 2",
        },
        {
            "page": 3,
            "deck_id": "d2",
            "page_in_deck": 1,
            "title": "Slide 3",
            "raw_text": "Content 3",
        },
    ]
    repo = LocalSlideRepository(slides=mock_slides)
    ctx = repo.build_context(page_number=1, query="Content 3")
    assert "deck=d1" in ctx
    assert "deck=d2" not in ctx


def test_retrieval_selected_text_priority():
    repo = LocalSlideRepository()
    sel_text = "ĐỌAN VĂN ĐẶC BIỆT CHỌN BỞI HỌC VIÊN"
    ctx = repo.build_context(page_number=1, selected_text=sel_text)
    assert "ĐOẠN HỌC VIÊN ĐÃ CHỌN (ƯU TIÊN CAO NHẤT)" in ctx
    assert sel_text in ctx


def test_retrieval_context_within_budget():
    repo = LocalSlideRepository()
    max_budget = 1000
    ctx = repo.build_context(page_number=1, max_chars=max_budget)
    assert len(ctx) <= max_budget + 100  # Within char limit budget


def test_retrieval_citation_page_mapping_correct():
    cit1 = {"citation_id": "c1", "source_id": "d1-p12", "snippet": "Key..."}
    assert _page_from_citation(cit1) == 12

    cit2 = {"citation_id": "c2", "source_location": "page=24", "snippet": "Value..."}
    assert _page_from_citation(cit2) == 24


def test_retrieval_two_slides_answer():
    repo = LocalSlideRepository()
    ctx = repo.build_context(page_number=3, query="Key và Value trong Transformer")
    assert "source_id=" in ctx
