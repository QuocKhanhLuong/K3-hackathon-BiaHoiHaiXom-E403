"""Full LangGraph flow end-to-end tests."""

import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from vlearn_ai.interface import VLearnAICore


@pytest.mark.asyncio
async def test_full_simple_flow():
    fake_llm = FakeListChatModel(responses=["Key là ma trận tra cứu."])
    ai_core = VLearnAICore(model=fake_llm)

    res = await ai_core.start_turn(
        thread_id="test_simple_1",
        question="Key là gì?",
        selected_context="Key dùng để so khớp với Query.",
    )
    assert res["status"] == "completed"
    assert res["route"]["name"] == "simple"
    assert res["assistant_message"] != ""
    json.dumps(res)  # Verify state JSON serializable


@pytest.mark.asyncio
async def test_clarification_flow_and_resume():
    fake_llm = FakeListChatModel(
        responses=["Bạn muốn hỏi phần nào?", "Giải thích chi tiết..."]
    )
    ai_core = VLearnAICore(model=fake_llm)

    # Step 1: Start turn with ambiguous query
    res1 = await ai_core.start_turn(
        thread_id="test_clar_1",
        question="Cái này hoạt động như thế nào?",
        selected_context="",
    )
    assert res1["status"] == "awaiting_clarification"
    json.dumps(res1)

    # Step 2: Resume turn with student clarification input
    res2 = await ai_core.resume_turn(
        thread_id="test_clar_1",
        student_input="Ý tôi là cơ chế Self-Attention trong bài 3.",
    )
    assert res2["status"] in ("awaiting_check", "completed")
    json.dumps(res2)


@pytest.mark.asyncio
async def test_check_flow_correct_answer():
    fake_llm = FakeListChatModel(
        responses=[
            "Key và Value khác nhau ở vai trò.",
            "Ví dụ Key-Value",
            "Micro-check question",
            "Gợi ý đào sâu 1",
        ]
    )
    ai_core = VLearnAICore(model=fake_llm)

    # Step 1: Start turn for check route
    res1 = await ai_core.start_turn(
        thread_id="test_check_correct_1",
        question="Key và Value khác nhau như thế nào?",
        selected_context="Key dùng để so khớp với Query, Value chứa nội dung được tổng hợp.",
    )
    assert res1["status"] == "awaiting_check"
    json.dumps(res1)

    # Step 2: Resume turn with correct student answer
    res2 = await ai_core.resume_turn(
        thread_id="test_check_correct_1",
        student_input="Lựa chọn A đúng theo tài liệu.",
    )
    assert res2["status"] == "completed"
    assert len(res2["followups"]) > 0
    json.dumps(res2)


@pytest.mark.asyncio
async def test_check_flow_incorrect_answer_and_retry_limit():
    fake_llm = FakeListChatModel(
        responses=[
            "Explanation...",
            "Example...",
            "Check 1...",
            "Repair 1 explanation...",
            "Check 2...",
            "Repair 2 explanation...",
            "Check 3...",
            "Repair 3 explanation...",
        ]
    )
    ai_core = VLearnAICore(model=fake_llm)

    thread_id = "test_check_incorrect_retry"

    # Turn 1: Start turn -> awaiting check (initial)
    res1 = await ai_core.start_turn(
        thread_id=thread_id,
        question="Key và Value khác nhau như thế nào?",
        selected_context="Key dùng để so khớp với Query, Value chứa nội dung.",
    )
    assert res1["status"] == "awaiting_check"

    # Turn 2: Incorrect answer 1 -> misconception repair -> new check (retry 1)
    res2 = await ai_core.resume_turn(
        thread_id=thread_id,
        student_input="Key và Value là một.",
    )
    assert res2["status"] == "awaiting_check"

    # Turn 3: Incorrect answer 2 -> misconception repair -> new check (retry 2)
    res3 = await ai_core.resume_turn(
        thread_id=thread_id,
        student_input="Vẫn nhầm lẫn giữa Key và Value.",
    )
    assert res3["status"] == "awaiting_check"

    # Turn 4: Incorrect answer 3 -> hits retry limit -> completed safely
    res4 = await ai_core.resume_turn(
        thread_id=thread_id,
        student_input="Tiếp tục trả lời sai.",
    )
    assert res4["status"] == "completed"
    assert res4.get("assistant_message") != ""
    json.dumps(res4)
