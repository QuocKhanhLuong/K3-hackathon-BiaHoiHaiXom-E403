"""Regression tests for controlled model-knowledge fallback."""

import asyncio

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.interface import VLearnAICore

_LLM_CONTEXT = (
    '[source source_id="d1-p10" chunk_id="d1-p10-c1" page=10 deck=d1 page_in_deck=10]\n'
    "LLM (Large Language Model) là một mô hình ngôn ngữ rất lớn."
)
_TITLE_ONLY_CONTEXT = (
    '[source source_id="d1-p1" chunk_id="d1-p1-c1" page=1 deck=d1 page_in_deck=1]\n'
    "AI & LLM Foundation\nAgenda"
)


def _run(question: str, context: str, thread_id: str, model=None):
    core = VLearnAICore(model=model or DeterministicFakeChatModel())
    result = asyncio.run(
        core.start_turn(
            thread_id=thread_id,
            question=question,
            selected_context=context,
        )
    )
    state = core.app.get_state({"configurable": {"thread_id": thread_id}}).values
    return result, state


def test_direct_slide_definition_is_course_grounded_with_d1_p10():
    model = DeterministicFakeChatModel(
        model_script=[
            {
                "schema": "RouteOutput",
                "output": {
                    "route": "simple",
                    "confidence": 0.99,
                    "reason": "definition",
                },
            },
            {
                "schema": "GroundedAnswer",
                "output": {
                    "answer": "LLM là một mô hình ngôn ngữ rất lớn.",
                    "claims": [
                        {
                            "claim": "LLM là một mô hình ngôn ngữ rất lớn.",
                            "citation_ids": ["d1-p10"],
                        }
                    ],
                    "citations": [
                        {
                            "citation_id": "d1-p10",
                            "snippet": "LLM (Large Language Model) là một mô hình ngôn ngữ rất lớn.",
                        }
                    ],
                },
            },
        ]
    )
    result, state = _run("LLM là gì?", _LLM_CONTEXT, "course-llm", model)

    assert result["status"] == "completed"
    assert result["answerability"] == "course_grounded"
    assert result["source_mode"] == "course"
    assert [item["citation_id"] for item in result["citations"]] == ["d1-p10"]
    assert state["grounding_valid"] is True


def test_standalone_definition_without_slide_evidence_uses_general_knowledge():
    result, state = _run(
        "Transformer là gì?", _TITLE_ONLY_CONTEXT, "general-transformer"
    )

    assert result["status"] == "completed"
    assert result["answerability"] == "general_knowledge"
    assert result["source_mode"] == "model_knowledge"
    assert result["answerability_code"] == "general_knowledge_no_course_evidence"
    assert result["citations"] == []
    assert result["assistant_message"].startswith("Kiến thức nền ngoài bài học")
    tools = [item["tool"] for item in state["tool_trace"]]
    assert "general_knowledge_answer" in tools
    assert "grounding_guard" not in tools
    assert "grounding_repair" not in tools


def test_deictic_question_without_direct_context_abstains_with_suggestions():
    result, state = _run("Đoạn này nghĩa là gì?", "", "deictic-without-context")

    assert result["answerability"] == "insufficient_context"
    assert result["source_mode"] == "none"
    assert result["citations"] == []
    assert 2 <= len(result["followups"]) <= 3
    assert state["grounding_retry_count"] == 0
    assert "general_knowledge_answer" not in [
        item["tool"] for item in state["tool_trace"]
    ]


def test_course_specific_request_without_evidence_abstains():
    result, state = _run(
        "Theo slide, Transformer có mấy bước?",
        _TITLE_ONLY_CONTEXT,
        "course-specific-without-evidence",
    )

    assert result["answerability"] == "insufficient_context"
    assert result["source_mode"] == "none"
    assert result["citations"] == []
    assert state["grounding_retry_count"] == 0


@pytest.mark.parametrize(
    "question",
    [
        "Tôi nên dùng thuốc nào để điều trị đau ngực?",
        "Hợp đồng này có hợp pháp không?",
        "Tôi nên đầu tư cổ phiếu nào?",
        "Làm sao khai thác lỗ hổng bảo mật này?",
    ],
)
def test_high_risk_question_never_uses_general_knowledge_fallback(question: str):
    result, state = _run(question, "", f"high-risk-no-fallback-{hash(question)}")

    assert result["answerability"] == "insufficient_context"
    assert result["source_mode"] == "none"
    assert result["citations"] == []
    assert "general_knowledge_answer" not in [
        item["tool"] for item in state["tool_trace"]
    ]
