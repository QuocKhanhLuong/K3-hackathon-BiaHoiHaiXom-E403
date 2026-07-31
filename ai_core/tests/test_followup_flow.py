"""Tests for post-response suggestion flow across AI Core routes and answerability states."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.graph.nodes import (
    _generate_fallback_answerable_followups,
    _generate_insufficient_context_followups,
    _normalize_followup_questions,
    router_node,
)
from vlearn_ai.interface import VLearnAICore

_VALID_CONTEXT = (
    '[source source_id="ctx_1" page=1 deck=d1 page_in_deck=1]\n'
    "Key dùng để so khớp với Query."
)

_NO_DEFINITION_CONTEXT = (
    '[source source_id="d1-p1" chunk_id="chunk_1" page=1 deck=d1 page_in_deck=1]\n'
    "AI IN ACTION - Day 1 AI & LLM Foundation"
)
_LLM_CONTEXT = (
    '[source source_id="d1-p10" chunk_id="d1-p10-c1" page=10 deck=d1 page_in_deck=10]\n'
    "LLM (Large Language Model) là một mô hình ngôn ngữ rất lớn."
)
_TUTOR_VOICE = ("bạn có thể", "bạn hãy", "theo bạn", "bạn muốn mình")


def test_router_overrides_check_for_explanatory_question():
    model = DeterministicFakeChatModel(
        model_script=[
            {
                "schema": "RouteOutput",
                "output": {
                    "route": "check",
                    "confidence": 0.9,
                    "reason": "incorrect model classification",
                },
            }
        ]
    )
    result = router_node(
        {
            "user_query": "Các thành phần chính của Transformer là gì?",
            "selected_context": _NO_DEFINITION_CONTEXT,
        },
        model,
    )

    assert result["route"] in {"simple", "deep"}
    assert result["route_source"] == "policy_override"


def test_router_keeps_check_only_for_explicit_assessment_request():
    model = DeterministicFakeChatModel(route_to_return="check")
    result = router_node(
        {
            "user_query": "Hãy kiểm tra hiểu biết của tôi bằng một quiz.",
            "selected_context": _NO_DEFINITION_CONTEXT,
        },
        model,
    )

    assert result["route"] == "check"


def test_router_overrides_clarify_for_complete_standalone_example_request():
    model = DeterministicFakeChatModel(
        model_script=[
            {
                "schema": "RouteOutput",
                "output": {
                    "route": "clarify",
                    "confidence": 0.9,
                    "reason": "incorrect model classification",
                },
            }
        ]
    )
    result = router_node(
        {
            "user_query": "Kể một ví dụ thực tế về cách LLM sinh nội dung.",
            "selected_context": _NO_DEFINITION_CONTEXT,
        },
        model,
    )

    assert result["route"] in {"simple", "deep"}
    assert result["route_source"] == "policy_override"


def test_all_deterministic_and_normalized_followups_are_learner_requests():
    state = {"user_query": "LLM là gì?"}
    generated = (
        _generate_insufficient_context_followups(state)
        + _generate_fallback_answerable_followups(state)
        + _normalize_followup_questions(
            [
                {
                    "label": "Mô tả",
                    "question": "Bạn có thể mô tả các thành phần chính của Transformer không?",
                }
            ]
        )
    )

    assert all(item["question"] for item in generated)
    assert all(
        not item["question"].casefold().startswith(_TUTOR_VOICE) for item in generated
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
        question="Đoạn này nghĩa là gì?",
        selected_context=_NO_DEFINITION_CONTEXT,
    )

    assert res["answerability"] == "insufficient_context"
    followups = res.get("followups") or []
    assert 2 <= len(followups) <= 3
    assert any(
        "Đoạn này" in f.get("question", "") or "Đoạn này" in f.get("label", "")
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


@pytest.mark.asyncio
async def test_suggestion_click_queries_stay_answerable_for_three_consecutive_turns():
    """Exercise the exact query field sent by a frontend suggestion chip."""
    ai_core = VLearnAICore(model=DeterministicFakeChatModel(route_to_return="simple"))
    response = await ai_core.start_turn(
        thread_id="suggestion-click-loop",
        question="LLM là gì?",
        selected_context=_LLM_CONTEXT,
    )

    assert response["answerability"] == "course_grounded"
    for turn in range(3):
        followups = response.get("followups") or []
        assert 2 <= len(followups) <= 3
        assert all(item.get("label") and item.get("question") for item in followups)
        assert all(
            not item["question"].casefold().startswith(_TUTOR_VOICE)
            for item in followups
        )

        # This is the frontend contract: send the original question, not label
        # or textContent rendered in the button.
        response = await ai_core.start_turn(
            thread_id=f"suggestion-click-loop-{turn}",
            question=followups[0]["question"],
            selected_context=_NO_DEFINITION_CONTEXT,
        )
        assert response["status"] == "completed"
        assert response["answerability"] in {"course_grounded", "general_knowledge"}
        assert response["route"]["name"] != "check"
        assert 2 <= len(response.get("followups") or []) <= 3
