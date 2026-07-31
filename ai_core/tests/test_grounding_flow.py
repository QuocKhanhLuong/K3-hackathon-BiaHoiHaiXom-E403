"""Grounding-flow tests for internal candidate diagnostics."""

import asyncio

from fake_model import DeterministicFakeChatModel
from vlearn_ai.interface import VLearnAICore


def test_candidate_output_survives_grounding_failure_and_is_not_public():
    core = VLearnAICore(model=DeterministicFakeChatModel())
    result = asyncio.run(
        core.start_turn(
            thread_id="candidate-failure",
            question="Khái niệm gì đó?",
            selected_context='[source source_id="other"]\nNội dung khác.',
        )
    )
    state = core.app.get_state(
        {"configurable": {"thread_id": "candidate-failure"}}
    ).values
    assert result["status"] == "failed"
    assert state["candidate_answer"] == "Key dùng để so khớp với Query."
    assert state["candidate_claims"]
    assert state["candidate_citations"]
    assert "candidate_answer" not in result
    assert "candidate_claims" not in result
    assert "candidate_citations" not in result


def test_title_only_definition_question_returns_insufficient_context_without_repair():
    core = VLearnAICore(model=DeterministicFakeChatModel())
    result = asyncio.run(
        core.start_turn(
            thread_id="title-only-definition",
            question="Embeddings là gì?",
            selected_context=(
                '[source source_id="d1-p1" chunk_id="d1-p1-c1" page=1 deck=d1 page_in_deck=1]\n'
                "Tiêu đề: Embeddings\nAgenda của bài học"
            ),
        )
    )
    state = core.app.get_state(
        {"configurable": {"thread_id": "title-only-definition"}}
    ).values
    assert result["status"] == "completed"
    assert result["citations"] == []
    assert state["answerability"] == "insufficient_context"
    assert state["answerability_code"] == "definition_evidence_missing"
    assert state["grounding_retry_count"] == 0


def test_candidate_output_resets_on_independent_new_turn():
    model = DeterministicFakeChatModel()
    core = VLearnAICore(model=model)
    thread_id = "candidate-reset"
    asyncio.run(
        core.start_turn(
            thread_id=thread_id,
            question="Khái niệm gì đó?",
            selected_context='[source source_id="other"]\nNội dung khác.',
        )
    )
    assert core.app.get_state({"configurable": {"thread_id": thread_id}}).values[
        "candidate_answer"
    ]

    model.route_to_return = "clarify"
    asyncio.run(
        core.start_turn(
            thread_id=thread_id,
            question="Cái này là gì?",
            selected_context='[source source_id="ctx_1"]\nKey dùng để so khớp với Query.',
        )
    )
    state = core.app.get_state({"configurable": {"thread_id": thread_id}}).values
    assert state["candidate_answer"] is None
    assert state["candidate_claims"] == []
    assert state["candidate_citations"] == []


def test_invalid_grounding_is_repaired_once_before_completion():
    model = DeterministicFakeChatModel(
        model_script=[
            {
                "schema": "RouteOutput",
                "output": {
                    "route": "simple",
                    "confidence": 0.99,
                    "reason": "factual question",
                },
            },
            {
                "schema": "GroundedAnswer",
                "output": {
                    "answer": "Key dùng để so khớp với Query.",
                    "claims": [
                        {
                            "claim": "Key dùng để so khớp với Query.",
                            "citation_ids": ["bad-id"],
                        }
                    ],
                    "citations": [
                        {
                            "citation_id": "bad-id",
                            "snippet": "Key dùng để so khớp với Query.",
                        }
                    ],
                },
            },
            {
                "schema": "GroundedAnswer",
                "output": {
                    "answer": "Key dùng để so khớp với Query.",
                    "claims": [
                        {
                            "claim": "Key dùng để so khớp với Query.",
                            "citation_ids": ["ctx_1"],
                        }
                    ],
                    "citations": [
                        {
                            "citation_id": "ctx_1",
                            "snippet": "Key dùng để so khớp với Query.",
                        }
                    ],
                },
            },
        ]
    )
    core = VLearnAICore(model=model)
    result = asyncio.run(
        core.start_turn(
            thread_id="candidate-repair",
            question="Key là gì?",
            selected_context='[source source_id="ctx_1"]\nKey dùng để so khớp với Query.',
        )
    )
    state = core.app.get_state(
        {"configurable": {"thread_id": "candidate-repair"}}
    ).values
    assert result["status"] == "completed"
    assert state["grounding_retry_count"] == 1
    assert state["candidate_citations"][0]["citation_id"] == "ctx_1"
    assert [trace["tool"] for trace in state["tool_trace"]].count(
        "grounding_repair"
    ) == 1


def test_conflicting_duplicate_source_is_repaired_to_one_d1_p10_citation():
    context = (
        '[source source_id="d1-p10" page=10 deck=d1 page_in_deck=10]\n'
        "LLM là mô hình ngôn ngữ lớn. LLM dựa trên Transformer."
    )
    model = DeterministicFakeChatModel(
        model_script=[
            {
                "schema": "RouteOutput",
                "output": {
                    "route": "simple",
                    "confidence": 0.99,
                    "reason": "factual question",
                },
            },
            {
                "schema": "GroundedAnswer",
                "output": {
                    "answer": "LLM là mô hình ngôn ngữ lớn. LLM dựa trên Transformer.",
                    "claims": [
                        {
                            "claim": "LLM là mô hình ngôn ngữ lớn.",
                            "citation_ids": ["d1-p10"],
                        },
                        {
                            "claim": "LLM dựa trên Transformer.",
                            "citation_ids": ["d1-p10"],
                        },
                    ],
                    "citations": [
                        {
                            "citation_id": "d1-p10",
                            "snippet": "LLM là mô hình ngôn ngữ lớn.",
                        },
                        {
                            "citation_id": "d1-p10",
                            "snippet": "LLM dựa trên Transformer.",
                        },
                    ],
                },
            },
            {
                "schema": "GroundedAnswer",
                "output": {
                    "answer": "LLM là mô hình ngôn ngữ lớn. LLM dựa trên Transformer.",
                    "claims": [
                        {
                            "claim": "LLM là mô hình ngôn ngữ lớn.",
                            "citation_ids": ["d1-p10"],
                        },
                        {
                            "claim": "LLM dựa trên Transformer.",
                            "citation_ids": ["d1-p10"],
                        },
                    ],
                    "citations": [
                        {
                            "citation_id": "d1-p10",
                            "snippet": "LLM là mô hình ngôn ngữ lớn. LLM dựa trên Transformer.",
                        }
                    ],
                },
            },
        ]
    )
    core = VLearnAICore(model=model)
    result = asyncio.run(
        core.start_turn(
            thread_id="duplicate-citation-repair",
            question="LLM là gì?",
            selected_context=context,
        )
    )
    state = core.app.get_state(
        {"configurable": {"thread_id": "duplicate-citation-repair"}}
    ).values
    assert result["status"] == "completed"
    assert state["grounding_valid"] is True
    assert state["grounding_retry_count"] == 1
    assert [citation["citation_id"] for citation in result["citations"]] == ["d1-p10"]
    assert [trace["tool"] for trace in state["tool_trace"]].count(
        "grounding_repair"
    ) == 1
