"""Offline API, contract, ownership, and SSE tests for Phase 0/1."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.ai.core_adapter import AICorePort, VLearnAICoreAdapter
from backend.app.application.turn_service import TurnService
from backend.app.config import BackendSettings
from backend.app.main import create_app
from backend.app.models import CoreInvocation
from backend.app.persistence.memory import MemoryRepository
from backend.app.retrieval.local_slides import LocalSlideRepository


class FakeAICore(AICorePort):
    def __init__(self):
        self.states: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return True

    @property
    def configured(self) -> bool:
        return True

    async def start_turn(
        self,
        *,
        thread_id: str,
        question: str,
        selected_context: str,
        conversation_history: list[dict[str, Any]],
    ) -> CoreInvocation:
        lowered = question.lower()
        if "clarify" in lowered or "làm rõ" in lowered:
            self.states[thread_id] = "clarification"
            return CoreInvocation(
                result={
                    "status": "awaiting_clarification",
                    "assistant_message": "Bạn muốn làm rõ khía cạnh nào?",
                    "route": {
                        "name": "clarify",
                        "confidence": 0.95,
                        "reason": "internal reason must not be public",
                    },
                    "ui_payload": {
                        "type": "clarification_request",
                        "question": "Bạn muốn làm rõ khía cạnh nào?",
                    },
                    "citations": [],
                    "followups": [],
                    "tool_trace": [{"tool": "router", "model": "private-model"}],
                },
                state={"clarification_question": "Bạn muốn làm rõ khía cạnh nào?"},
            )
        if "check" in lowered or "khác nhau" in lowered:
            return self._check(thread_id)
        if "deep" in lowered or "tại sao" in lowered:
            return CoreInvocation(
                result={
                    "status": "completed",
                    "assistant_message": "Giải thích chuyên sâu có căn cứ.",
                    "route": {"name": "deep", "confidence": 0.9, "reason": "private"},
                    "citations": [
                        {
                            "citation_id": "page_1",
                            "snippet": "Nội dung slide kiểm thử.",
                            "source_location": "trang 1",
                        }
                    ],
                    "followups": [
                        {"label": "Mở rộng", "question": "Tìm hiểu sâu hơn?"}
                    ],
                    "tool_trace": [{"tool": "router"}],
                },
                state={},
            )
        return CoreInvocation(
            result={
                "status": "completed",
                "assistant_message": "Câu trả lời ngắn có căn cứ.",
                "route": {"name": "simple", "confidence": 0.99, "reason": "private"},
                "citations": [
                    {
                        "citation_id": "page_1",
                        "snippet": "Nội dung slide kiểm thử.",
                        "source_location": "trang 1",
                    }
                ],
                "followups": [],
                "tool_trace": [{"tool": "router", "model": "private-model"}],
            },
            state={},
        )

    async def resume_turn(
        self, *, thread_id: str, student_input: str
    ) -> CoreInvocation:
        if self.states.get(thread_id) == "clarification":
            return self._check(thread_id)
        if student_input == "opt_a":
            return CoreInvocation(
                result={
                    "status": "completed",
                    "assistant_message": "Đúng rồi.",
                    "route": {"name": "check", "confidence": 0.95, "reason": "private"},
                    "citations": [],
                    "followups": [
                        {"label": "Tiếp tục", "question": "Câu hỏi tiếp theo?"}
                    ],
                    "tool_trace": [{"tool": "validate_understanding"}],
                },
                state={
                    "last_check_result": {
                        "is_correct": True,
                        "score": 1.0,
                        "misconception_code": "none",
                    }
                },
            )
        return CoreInvocation(
            result={
                "status": "awaiting_check",
                "assistant_message": "Hãy xem lại khái niệm và thử lại.",
                "route": {"name": "check", "confidence": 0.95, "reason": "private"},
                "ui_payload": {
                    "type": "multiple_choice",
                    "question": "Câu kiểm tra lại?",
                    "options": [
                        {"option_id": "opt_a", "text": "Đáp án đúng mới"},
                        {"option_id": "opt_b", "text": "Đáp án sai mới"},
                    ],
                },
                "citations": [],
                "followups": [],
                "tool_trace": [{"tool": "repair_misconception"}],
            },
            state={
                "last_check_result": {
                    "is_correct": False,
                    "score": 0.0,
                    "misconception_code": "concept_confusion",
                },
                "check_question": {
                    "question": "Câu kiểm tra lại?",
                    "question_type": "multiple_choice",
                    "target_concept": "concept",
                    "expected_answer": "Đáp án đúng mới",
                    "correct_option_id": "opt_a",
                    "options": [
                        {"option_id": "opt_a", "text": "Đáp án đúng mới"},
                        {"option_id": "opt_b", "text": "Đáp án sai mới"},
                    ],
                    "explanation": "Private explanation",
                    "evidence": ["Private evidence"],
                },
            },
        )

    def _check(self, thread_id: str) -> CoreInvocation:
        self.states[thread_id] = "check"
        check = {
            "question": "Phương án nào đúng?",
            "question_type": "multiple_choice",
            "target_concept": "concept",
            "expected_answer": "Đáp án A",
            "correct_option_id": "opt_a",
            "options": [
                {"option_id": "opt_a", "text": "Đáp án A"},
                {"option_id": "opt_b", "text": "Đáp án B"},
            ],
            "explanation": "Private explanation",
            "evidence": ["Private evidence"],
        }
        return CoreInvocation(
            result={
                "status": "awaiting_check",
                "assistant_message": "Phần giải thích trước câu kiểm tra.",
                "route": {"name": "check", "confidence": 0.95, "reason": "private"},
                "ui_payload": {
                    "type": "multiple_choice",
                    "question": check["question"],
                    "options": check["options"],
                },
                "citations": [],
                "followups": [],
                "tool_trace": [{"tool": "router", "model": "private-model"}],
            },
            state={"check_question": check},
        )


@pytest.fixture
def app():
    slides = LocalSlideRepository(
        [
            {
                "page": 1,
                "deck_id": "test",
                "page_in_deck": 1,
                "title": "Slide test",
                "subtitle": "",
                "raw_text": "Nội dung slide kiểm thử.",
                "content": "<p>Nội dung slide kiểm thử.</p>",
                "code": "missing.pdf#page=1",
            }
        ]
    )
    service = TurnService(MemoryRepository(), FakeAICore(), slides)
    settings = BackendSettings(
        serve_frontend=False,
        anonymous_session_secret="test-session-secret",
    )
    return create_app(settings=settings, turn_service=service, slide_repository=slides)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def _create_conversation(client: TestClient) -> str:
    response = client.post("/api/v1/conversations", json={"course_id": "test"})
    assert response.status_code == 201
    return response.json()["conversation_id"]


def test_real_adapter_initializes_against_public_ai_core():
    adapter = VLearnAICoreAdapter()
    assert adapter.available is True


def test_v1_simple_contract_strips_internal_trace_and_reason(client: TestClient):
    conversation_id = _create_conversation(client)
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/turns",
        json={"question": "Câu hỏi đơn giản", "page_number": 1},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "completed"
    assert body["route"] == {"name": "simple", "confidence": 0.99}
    encoded = response.text
    assert "tool_trace" not in encoded
    assert "private-model" not in encoded
    assert "internal reason" not in encoded
    assert "correct_option" not in encoded


def test_quiz_answer_is_private_and_server_scores_by_action(client: TestClient):
    conversation_id = _create_conversation(client)
    first = client.post(
        f"/api/v1/conversations/{conversation_id}/turns",
        json={"question": "check kiến thức", "page_number": 1},
    )
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["status"] == "awaiting_response"
    assert first_body["action"]["options"][0] == {
        "id": "opt_a",
        "text": "Đáp án A",
    }
    assert "correct_option_id" not in first.text
    assert "expected_answer" not in first.text
    assert "explanation" not in first.text

    submitted = client.post(
        f"/api/v1/turns/{first_body['turn_id']}/responses",
        json={
            "action_id": first_body["action"]["action_id"],
            "value": "opt_a",
            "idempotency_key": "idem-correct-answer",
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "completed"
    assert submitted.json()["suggestions"] == ["Câu hỏi tiếp theo?"]


def test_legacy_quiz_rejects_client_supplied_correct_answer(client: TestClient):
    started = client.post(
        "/api/tutor/ask",
        json={"question": "check kiến thức", "page_number": 1},
    )
    quiz = started.json()["tool_data"]
    assert "correct_index" not in quiz
    assert "expected_keywords" not in quiz

    rejected = client.post(
        "/api/quiz/submit",
        json={
            "quiz_id": quiz["quiz_id"],
            "quiz_type": "multiple_choice",
            "selected_option": 0,
            "correct_option": 0,
            "question_text": quiz["question"],
            "page_number": 1,
        },
    )
    assert rejected.status_code == 422


def test_legacy_clarification_contract_and_resume(client: TestClient):
    first = client.post(
        "/api/tutor/ask",
        json={"question": "clarify giúp mình", "page_number": 1},
    )
    assert first.status_code == 200
    body = first.json()
    tool = body["tool_data"]
    assert tool["clarifying_question"]
    assert len(tool["suggested_inputs"]) == 3
    assert "question" not in tool

    resumed = client.post(
        "/api/tutor/ask",
        json={
            "question": tool["suggested_inputs"][0],
            "page_number": 1,
            "thread_id": body["thread_id"],
        },
    )
    assert resumed.status_code == 200
    assert resumed.json()["tool_data"]["quiz_id"].startswith("action_")


def test_sse_has_safe_progress_and_one_result(client: TestClient):
    response = client.post(
        "/api/tutor/ask/stream",
        json={"question": "Câu hỏi đơn giản", "page_number": 1},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count('"type": "result"') == 1
    assert '"type": "trace"' in response.text
    assert "private-model" not in response.text
    assert "tool_trace" not in response.text


def test_conversation_is_scoped_to_signed_anonymous_session(app):
    with TestClient(app) as first_client:
        conversation_id = _create_conversation(first_client)
    with TestClient(app) as second_client:
        response = second_client.get(f"/api/v1/conversations/{conversation_id}")
    assert response.status_code == 404


def test_idempotent_action_response_does_not_resume_twice(client: TestClient):
    conversation_id = _create_conversation(client)
    first = client.post(
        f"/api/v1/conversations/{conversation_id}/turns",
        json={"question": "check kiến thức", "page_number": 1},
    ).json()
    payload = {
        "action_id": first["action"]["action_id"],
        "value": "opt_a",
        "idempotency_key": "same-response-key",
    }
    url = f"/api/v1/turns/{first['turn_id']}/responses"
    response_one = client.post(url, json=payload)
    response_two = client.post(url, json=payload)
    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert response_one.json()["turn_id"] == response_two.json()["turn_id"]
