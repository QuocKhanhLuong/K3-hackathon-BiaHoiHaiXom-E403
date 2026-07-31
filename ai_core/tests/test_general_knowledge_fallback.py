"""Regression tests for controlled model-knowledge fallback."""

import asyncio

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.interface import VLearnAICore

_LLM_CONTEXT = (
    '[source source_id="d1-p10" chunk_id="d1-p10-c1" page=10 deck=d1 page_in_deck=10]\n'
    "LLM (Large Language Model) là một mô hình ngôn ngữ rất lớn,\n"
    "thường dựa trên kiến trúc Transformer."
)
_TITLE_ONLY_CONTEXT = (
    '[source source_id="d1-p1" chunk_id="d1-p1-c1" page=1 deck=d1 page_in_deck=1]\n'
    "AI & LLM Foundation\nAgenda"
)
_PROCESS_QUERY = (
    "Mô tả ngắn gọn cách một LLM được huấn luyện từ pre-training đến "
    "fine-tuning (SFT/RLHF) và tại sao các bước này quan trọng"
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
    model = DeterministicFakeChatModel()
    result, state = _run("LLM là gì?", _LLM_CONTEXT, "course-llm", model)

    assert result["status"] == "completed"
    assert result["answerability"] == "course_grounded"
    assert result["source_mode"] == "course"
    assert [item["citation_id"] for item in result["citations"]] == ["d1-p10"]
    assert state["grounding_valid"] is True
    assert state["grounding_retry_count"] == 0
    assert state["candidate_answer"] == result["assistant_message"]
    assert result["assistant_message"] == (
        "LLM (Large Language Model) là một mô hình ngôn ngữ rất lớn, "
        "thường dựa trên kiến trúc Transformer."
    )


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


def test_standalone_training_process_without_direct_evidence_uses_general_knowledge():
    model = DeterministicFakeChatModel(
        model_script=[
            {
                "schema": "RouteOutput",
                "output": {
                    "route": "simple",
                    "confidence": 0.99,
                    "reason": "standalone process question",
                },
            },
            {
                "schema": "GeneralKnowledgeAnswer",
                "output": {
                    "answer": "Pre-training học quy luật ngôn ngữ từ dữ liệu lớn; "
                    "SFT và RLHF tiếp tục căn chỉnh cách mô hình phản hồi."
                },
            },
        ]
    )
    result, state = _run(
        _PROCESS_QUERY, _TITLE_ONLY_CONTEXT, "general-training-process", model
    )

    assert result["status"] == "completed"
    assert result["answerability"] == "general_knowledge"
    assert result["source_mode"] == "model_knowledge"
    assert result["citations"] == []
    assert result["assistant_message"].startswith("Kiến thức nền ngoài bài học")
    assert 2 <= len(result["followups"]) <= 3
    assert state["grounding_retry_count"] == 0
    assert "grounding_guard" not in [item["tool"] for item in state["tool_trace"]]


@pytest.mark.parametrize(
    "question",
    [
        "Kể một ví dụ thực tế về cách LLM được dùng để sinh nội dung và một hạn chế cần lưu ý.",
        "Các thành phần chính của Transformer và vai trò của từng thành phần là gì?",
        "Mô tả ngắn gọn quá trình pre-training, SFT và RLHF.",
    ],
)
def test_standalone_explanatory_queries_use_general_knowledge_without_evidence(
    question: str,
):
    result, state = _run(
        question, _TITLE_ONLY_CONTEXT, f"standalone-explanation-{hash(question)}"
    )

    assert result["status"] == "completed"
    assert result["answerability"] == "general_knowledge"
    assert result["source_mode"] == "model_knowledge"
    assert result["citations"] == []
    assert result["route"]["name"] != "check"
    assert 2 <= len(result["followups"]) <= 3
    assert state["grounding_retry_count"] == 0


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
