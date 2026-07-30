"""Offline regression coverage for deck-wide evidence retrieval."""

from __future__ import annotations

import asyncio
import re

from backend.app.retrieval.local_slides import LocalSlideRepository
from eval.runner import ScenarioRunner
from eval.schemas import (
    ContextFixture,
    ContextSlideFixture,
    OfflineFixture,
    ScenarioDefinition,
    ScenarioTurn,
    ScriptedOutput,
    TurnExpectations,
)


def _source_ids(context: str) -> list[str]:
    return re.findall(r'source_id="([^"]+)"', context)


def _slide(
    page: int,
    title: str,
    raw_text: str,
    *,
    deck_id: str = "d1",
    source_id: str | None = None,
) -> dict[str, object]:
    return {
        "source_id": source_id or f"{deck_id}-p{page}",
        "deck_id": deck_id,
        "page": page,
        "page_in_deck": page,
        "title": title,
        "raw_text": raw_text,
    }


def _llm_deck() -> list[dict[str, object]]:
    return [
        _slide(5, "Láng giềng trước", "Một mốc lịch sử không liên quan."),
        _slide(6, "Slide đang xem", "Hệ chuyên gia trong lịch sử AI."),
        _slide(7, "Láng giềng sau", "Ảnh và dữ liệu huấn luyện."),
        _slide(10, "LLM", "LLM là gì? LLM là mô hình ngôn ngữ lớn."),
    ]


def test_cross_slide_semantic_retrieval_keeps_current_as_anchor():
    context = LocalSlideRepository(slides=_llm_deck()).build_context(
        page_number=6, deck_id="d1", query="LLM là gì?"
    )

    # The answer slide is selected from the whole deck before either neighbor.
    assert _source_ids(context) == ["d1-p6", "d1-p10", "d1-p5", "d1-p7"]


def test_direct_ai_core_eval_cites_answer_slide_not_current_slide():
    slides = [ContextSlideFixture(**slide) for slide in _llm_deck()]
    scenario = ScenarioDefinition(
        id="RETRIEVAL-DECK-WIDE-001",
        name="Cross-slide LLM definition",
        description="The AI Core receives and cites evidence from another slide.",
        mode="offline",
        deck_id="d1",
        start_page=6,
        offline_fixture=OfflineFixture(
            context_fixture=ContextFixture(type="synthetic_slides", slides=slides),
            model_script=[
                ScriptedOutput(
                    schema="RouteOutput",
                    output={
                        "route": "simple",
                        "confidence": 0.99,
                        "reason": "Factual definition",
                    },
                ),
                ScriptedOutput(
                    schema="GroundedAnswer",
                    output={
                        "answer": "LLM là mô hình ngôn ngữ lớn.",
                        "claims": [
                            {
                                "claim": "LLM là mô hình ngôn ngữ lớn.",
                                "citation_ids": ["d1-p10"],
                            }
                        ],
                        "citations": [
                            {
                                "citation_id": "d1-p10",
                                "snippet": "LLM là mô hình ngôn ngữ lớn.",
                            }
                        ],
                    },
                ),
            ],
        ),
        turns=[
            ScenarioTurn(
                type="user_turn",
                input="LLM là gì?",
                expected=TurnExpectations(
                    routes=["simple"],
                    statuses=["completed"],
                    required_source_ids=["d1-p10"],
                    min_citations=1,
                    grounding_required=True,
                ),
            )
        ],
    )

    result = asyncio.run(ScenarioRunner(mode="offline").run_scenario(scenario))
    turn = result.turn_results[0]
    assert result.passed is True
    assert turn.retrieved_sources[:2] == ["d1-p6", "d1-p10"]
    assert turn.citation_ids == ["d1-p10"]


def test_explicit_page_reference_has_highest_source_priority():
    context = LocalSlideRepository(slides=_llm_deck()).build_context(
        page_number=6, deck_id="d1", query="Giải thích slide 10"
    )

    assert _source_ids(context)[0] == "d1-p10"


def test_selected_text_and_current_slide_are_contextual_priority():
    selected_text = "Câu này cần được giải thích theo ngữ cảnh đang chọn."
    context = LocalSlideRepository(slides=_llm_deck()).build_context(
        page_number=6,
        deck_id="d1",
        query="đoạn này nghĩa là gì?",
        selected_text=selected_text,
    )

    assert context.index(selected_text) < context.index('[source source_id="d1-p6"')
    assert _source_ids(context)[0] == "d1-p6"


def test_same_deck_isolation_and_exact_fixture_source_ids():
    slides = _llm_deck() + [
        _slide(
            1,
            "LLM ở deck khác",
            "LLM là gì? LLM ở deck khác.",
            deck_id="d2",
            source_id="exact-d2-source",
        )
    ]
    context = LocalSlideRepository(slides=slides).build_context(
        page_number=6, deck_id="d1", query="LLM là gì?"
    )

    assert "exact-d2-source" not in _source_ids(context)
    assert "d2" not in context
    assert "d1-p10" in _source_ids(context)


def test_semantic_ranking_is_preserved_before_top_k_truncation():
    slides = [
        _slide(8, "Anchor", "Không có thuật ngữ truy vấn."),
        _slide(1, "One", "vector"),
        _slide(2, "Two", "vector vector"),
        _slide(3, "Three", "vector vector vector"),
        _slide(7, "Neighbor", "Không có thuật ngữ truy vấn."),
        _slide(9, "Neighbor", "Không có thuật ngữ truy vấn."),
    ]
    context = LocalSlideRepository(slides=slides).build_context(
        page_number=8, deck_id="d1", query="vector", max_slides=3
    )

    # A deck-order rebuild would produce p1 then p2.  The top-k bundle keeps
    # the semantic order p3 then p2 after the current-slide anchor instead.
    assert _source_ids(context) == ["d1-p8", "d1-p3", "d1-p2"]


def test_duplicate_source_ids_are_not_emitted_twice():
    slides = [
        _slide(6, "Anchor", "Nội dung hiện tại.", source_id="anchor"),
        _slide(10, "LLM", "LLM là gì?", source_id="answer"),
        _slide(11, "Duplicate", "LLM là gì?", source_id="answer"),
    ]
    context = LocalSlideRepository(slides=slides).build_context(
        page_number=6, deck_id="d1", query="LLM là gì?"
    )

    assert _source_ids(context).count("answer") == 1
