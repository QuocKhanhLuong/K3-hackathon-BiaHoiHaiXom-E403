"""Tests for post-response suggestion flow across AI Core routes and answerability states."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.interface import VLearnAICore

_VALID_CONTEXT = (
    '[source source_id="ctx_1" page=1 deck=d1 page_in_deck=1]\n'
    "Key dùng để so khớp với Query."
)

_CHUNK_CONTEXT = (
    '[source source_id="d1-p1" chunk_id="chunk_1" page=1 deck=d1 page_in_deck=1]\n'
    "AI IN ACTION - Day 1 AI & LLM Foundation"
)


@pytest.mark.asyncio
async def test_simple_answerable_response_has_followups():
    fake_llm = DeterministicFakeChatModel(route_to_return="simple")
    ai_core = VLearnAICore(model=fake_llm)

    res = await ai_core.start_turn(
        thread_id="test_followup_simple",
        question="Key dùng để làm gì?",
        selected_context=_VALID_CONTEXT,
    )

    assert res["status"] == "completed"
    followups = res.get("followups") or []
    assert 2 <= len(followups) <= 3
    assert all("question" in f or "label" in f for f in followups)


@pytest.mark.asyncio
async def test_deep_answerable_response_has_followups():
    fake_llm = DeterministicFakeChatModel(route_to_return="deep")
    ai_core = VLearnAICore(model=fake_llm)

    res = await ai_core.start_turn(
        thread_id="test_followup_deep",
        question="Giải thích chi tiết về Key và Query",
        selected_context=_VALID_CONTEXT,
    )

    assert res["status"] == "completed"
    followups = res.get("followups") or []
    assert 2 <= len(followups) <= 3


@pytest.mark.asyncio
async def test_insufficient_context_has_deterministic_suggestions_without_extra_llm_call():
    fake_llm = DeterministicFakeChatModel(route_to_return="simple")
    ai_core = VLearnAICore(model=fake_llm)

    res = await ai_core.start_turn(
        thread_id="test_followup_insufficient",
        question="Quantum Computing là gì?",
        selected_context=_CHUNK_CONTEXT,
    )

    assert res["answerability"] == "insufficient_context"
    followups = res.get("followups") or []
    assert 2 <= len(followups) <= 3
    assert any(
        "Quantum Computing" in f.get("question", "")
        or "Quantum Computing" in f.get("label", "")
        for f in followups
    )
    trace_tools = [t.get("tool") for t in res.get("tool_trace", [])]
    assert "suggest_followups" in trace_tools


@pytest.mark.asyncio
async def test_awaiting_clarification_or_check_has_no_followups():
    fake_llm = DeterministicFakeChatModel(route_to_return="clarify")
    ai_core = VLearnAICore(model=fake_llm)

    res_clar = await ai_core.start_turn(
        thread_id="test_followup_clarify",
        question="Cái này là sao?",
        selected_context=_VALID_CONTEXT,
    )
    assert res_clar["status"] == "awaiting_clarification"
    assert res_clar.get("followups") == []

    fake_llm_check = DeterministicFakeChatModel(route_to_return="check")
    ai_core_check = VLearnAICore(model=fake_llm_check)
    res_check = await ai_core_check.start_turn(
        thread_id="test_followup_check",
        question="Hãy kiểm tra hiểu biết của tôi",
        selected_context=_VALID_CONTEXT,
    )
    assert res_check["status"] == "awaiting_check"
    assert res_check.get("followups") == []
