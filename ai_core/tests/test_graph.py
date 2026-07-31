"""Integration tests for VLearn AI Core LangGraph workflow orchestration."""

import json

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.interface import VLearnAICore
from vlearn_ai.schemas import InvalidResumeStateError, ToolTrace


@pytest.mark.asyncio
async def test_full_simple_flow():
    fake_llm = DeterministicFakeChatModel(route_to_return="simple")
    ai_core = VLearnAICore(model=fake_llm)

    res = await ai_core.start_turn(
        thread_id="test_simple_1",
        question="Transformer là gì?",
        selected_context='[source source_id="ctx_1"]\nKey dùng để so khớp với Query.',
    )

    assert res["status"] == "completed"
    assert res["route"]["name"] == "simple"
    assert res["assistant_message"] != ""
    assert len(res["citations"]) > 0
    assert len(res["tool_trace"]) > 0
    for trace in res["tool_trace"]:
        ToolTrace(**trace)
    json.dumps(res)


@pytest.mark.asyncio
async def test_clarification_flow_and_resume():
    fake_llm = DeterministicFakeChatModel(route_to_return="clarify")
    ai_core = VLearnAICore(model=fake_llm)

    # Step 1: Start turn -> pauses at awaiting_clarification
    res1 = await ai_core.start_turn(
        thread_id="test_clar_1",
        question="Cái này là gì?",
        selected_context='[source source_id="ctx_1"]\nKey dùng để so khớp với Query.',
    )

    assert res1["status"] == "awaiting_clarification"
    assert res1["ui_payload"]["type"] == "clarification_request"
    assert res1["ui_payload"]["question"] != ""

    # Step 2: Resume turn with student clarification answer
    res2 = await ai_core.resume_turn(
        thread_id="test_clar_1",
        student_input="Tôi muốn hỏi về cơ chế Attention",
    )

    assert res2["status"] == "awaiting_check"
    assert res2["ui_payload"]["question"] != ""
    json.dumps(res2)

    # Step 3: Resume the generated check and complete the turn
    res3 = await ai_core.resume_turn(
        thread_id="test_clar_1",
        student_input="opt_a",
    )

    assert res3["status"] == "completed"
    assert res3["assistant_message"] != ""
    json.dumps(res3)


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
        selected_context='[source source_id="ctx_1"]\nKey dùng để so khớp với Query.',
    )

    assert res1["status"] == "awaiting_check"
    assert res1["ui_payload"]["type"] == "multiple_choice"
    assert res1["ui_payload"]["question"] != ""
    json.dumps(res1)

    # Step 2: Resume turn with correct student answer
    res2 = await ai_core.resume_turn(
        thread_id="test_check_correct_1",
        student_input="opt_a",
    )

    assert res2["status"] == "completed"
    assert res2["assistant_message"] != ""
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
        selected_context='[source source_id="ctx_1"]\nKey dùng để so khớp với Query.',
    )
    assert res1["status"] == "awaiting_check"

    # Turn 2: Resume with incorrect answer -> misconception repair -> awaiting_check (retry 1)
    res2 = await ai_core.resume_turn(
        thread_id=thread_id,
        student_input="Key và Value là một.",
    )
    assert res2["status"] == "awaiting_check"
    assert "Ví dụ minh họa (giả định):" in res2["assistant_message"]
    assert "Ví dụ minh họa Key-Value" in res2["assistant_message"]
    repair_state = ai_core.app.get_state(
        {"configurable": {"thread_id": thread_id}}
    ).values
    assert repair_state["grounding_valid"] is True
    assert repair_state["supplemental_actions"]["illustrative_example"]
    assert repair_state["grounded_claims"]
    assert [trace["tool"] for trace in repair_state["tool_trace"]].count(
        "give_example"
    ) == 1
    assert [trace["tool"] for trace in repair_state["tool_trace"]].count(
        "repair_misconception"
    ) == 1
    for trace in repair_state["tool_trace"]:
        ToolTrace(**trace)

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


@pytest.mark.asyncio
async def test_invalid_resume_thread_id_raises_error():
    fake_llm = DeterministicFakeChatModel()
    ai_core = VLearnAICore(model=fake_llm)

    with pytest.raises(InvalidResumeStateError):
        await ai_core.resume_turn(
            thread_id="non_existent_thread",
            student_input="opt_a",
        )


@pytest.mark.asyncio
async def test_grounding_failure_flow():
    fake_llm = DeterministicFakeChatModel(route_to_return="simple")
    ai_core = VLearnAICore(model=fake_llm)

    # Context does NOT contain the citation snippet returned by fake_llm
    res = await ai_core.start_turn(
        thread_id="test_grounding_fail_1",
        question="Khái niệm gì đó?",
        selected_context="Nội dung bối cảnh hoàn toàn khác không chứa từ khóa.",
    )

    assert res["status"] == "failed"
    assert "Ngữ cảnh bài học hiện tại chưa đủ" in res["assistant_message"]
