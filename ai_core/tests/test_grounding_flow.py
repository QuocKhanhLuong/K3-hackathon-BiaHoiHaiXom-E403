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
                "output": {"route": "simple", "confidence": 0.99, "reason": "factual question"},
            },
            {
                "schema": "GroundedAnswer",
                "output": {
                    "answer": "Key dùng để so khớp với Query.",
                    "claims": [{"claim": "Key dùng để so khớp với Query.", "citation_ids": ["bad-id"]}],
                    "citations": [{"citation_id": "bad-id", "snippet": "Key dùng để so khớp với Query."}],
                },
            },
            {
                "schema": "GroundedAnswer",
                "output": {
                    "answer": "Key dùng để so khớp với Query.",
                    "claims": [{"claim": "Key dùng để so khớp với Query.", "citation_ids": ["ctx_1"]}],
                    "citations": [{"citation_id": "ctx_1", "snippet": "Key dùng để so khớp với Query."}],
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
    state = core.app.get_state({"configurable": {"thread_id": "candidate-repair"}}).values
    assert result["status"] == "completed"
    assert state["grounding_retry_count"] == 1
    assert state["candidate_citations"][0]["citation_id"] == "ctx_1"
    assert [trace["tool"] for trace in state["tool_trace"]].count("grounding_repair") == 1
