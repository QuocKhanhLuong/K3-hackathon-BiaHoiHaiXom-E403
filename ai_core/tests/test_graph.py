"""End-to-end native LangGraph flow and interrupt/resume tests."""

import json

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.interface import VLearnAICore
from vlearn_ai.schemas import InvalidResumeStateError


@pytest.mark.asyncio
async def test_full_simple_flow():
    fake_llm = DeterministicFakeChatModel(route_to_return="simple")
    ai_core = VLearnAICore(model=fake_llm)

    res = await ai_core.start_turn(
        thread_id="test_simple_1",
        question="Key là gì?",
        selected_context="Key dùng để so khớp với Query.",
    )
    assert res["status"] == "completed"
    assert res["route"]["name"] == "simple"
    assert res["assistant_message"] != ""
    json.dumps(res)  # Verify JSON serializability


@pytest.mark.asyncio
async def test_clarification_flow_and_resume():
    fake_llm = DeterministicFakeChatModel(route_to_return="clarify")
    ai_core = VLearnAICore(model=fake_llm)

    # Step 1: Start turn -> pauses at await_clarification
    res1 = await ai_core.start_turn(
        thread_id="test_clar_1",
        question="Cái này hoạt động như thế nào?",
        selected_context="Bối cảnh bài học",
    )
    assert res1["status"] == "awaiting_clarification"
    assert res1["ui_payload"]["type"] == "clarification_request"
    json.dumps(res1)

    # Step 2: Resume turn with student clarification answer
    res2 = await ai_core.resume_turn(
        thread_id="test_clar_1",
        student_input="Ý tôi là cơ chế Self-Attention trong bài 3.",
    )
    assert res2["status"] in ("awaiting_check", "completed")
    json.dumps(res2)


@pytest.mark.asyncio
async def test_check_flow_correct_answer():
    fake_llm = DeterministicFakeChatModel(
        route_to_return="check", misconception_to_return=False
    )
    ai_core = VLearnAICore(model=fake_llm)

    # Step 1: Start turn -> pauses at await_check
    res1 = await ai_core.start_turn(
        thread_id="test_check_correct_1",
        question="Key và Value khác nhau như thế nào?",
        selected_context="Key dùng để so khớp với Query, Value chứa nội dung.",
    )
    assert res1["status"] == "awaiting_check"
    assert res1["ui_payload"]["question"] != ""
    json.dumps(res1)

    # Step 2: Resume turn with correct student answer
    res2 = await ai_core.resume_turn(
        thread_id="test_check_correct_1",
        student_input="opt_a",
    )
    assert res2["status"] == "completed"
    assert len(res2["followups"]) >= 2
    json.dumps(res2)


@pytest.mark.asyncio
async def test_check_flow_incorrect_answer_and_retry_limit():
    fake_llm = DeterministicFakeChatModel(
        route_to_return="check", misconception_to_return=True
    )
    ai_core = VLearnAICore(model=fake_llm)

    thread_id = "test_check_incorrect_retry"

    # Turn 1: Start turn -> awaiting_check (initial)
    res1 = await ai_core.start_turn(
        thread_id=thread_id,
        question="Key và Value khác nhau như thế nào?",
        selected_context="Key dùng để so khớp với Query, Value chứa nội dung.",
    )
    assert res1["status"] == "awaiting_check"

    # Turn 2: Resume with incorrect answer -> misconception repair -> awaiting_check (retry 1)
    res2 = await ai_core.resume_turn(
        thread_id=thread_id,
        student_input="Key và Value là một.",
    )
    assert res2["status"] == "awaiting_check"

    # Turn 3: Resume with incorrect answer -> misconception repair -> awaiting_check (retry 2)
    res3 = await ai_core.resume_turn(
        thread_id=thread_id,
        student_input="Vẫn nhầm lẫn.",
    )
    assert res3["status"] == "awaiting_check"

    # Turn 4: Resume with incorrect answer -> hits retry limit -> completed (safe_end)
    res4 = await ai_core.resume_turn(
        thread_id=thread_id,
        student_input="Lại sai tiếp.",
    )
    assert res4["status"] == "completed"
    assert "đọc lại tài liệu" in (res4.get("assistant_message") or "")
    json.dumps(res4)


@pytest.mark.asyncio
async def test_invalid_resume_thread_id_raises_error():
    fake_llm = DeterministicFakeChatModel()
    ai_core = VLearnAICore(model=fake_llm)

    with pytest.raises(InvalidResumeStateError):
        await ai_core.resume_turn(
            thread_id="non_existent_thread_id",
            student_input="Test answer",
        )
