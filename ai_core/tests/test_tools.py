"""Unit tests for the 6 pedagogical tools."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from vlearn_ai.schemas import CheckEvaluation, GroundedAnswer, MicroCheck
from vlearn_ai.tools.give_direct_answer import execute_give_direct_answer
from vlearn_ai.tools.give_example import execute_give_example
from vlearn_ai.tools.give_hint import execute_give_hint
from vlearn_ai.tools.motivate import execute_motivate
from vlearn_ai.tools.review_concept import execute_review_concept
from vlearn_ai.tools.validate_understanding import execute_validate_understanding


@pytest.mark.asyncio
async def test_tool_review_concept():
    fake_llm = FakeListChatModel(responses=["Khái niệm Key trong Attention..."])
    res = await execute_review_concept(
        query="Key là gì?",
        context="Key dùng để so khớp với Query.",
        model=fake_llm,
    )
    assert isinstance(res, GroundedAnswer)
    assert len(res.answer) > 0


@pytest.mark.asyncio
async def test_tool_give_direct_answer():
    fake_llm = FakeListChatModel(
        responses=["Key là ma trận biểu diễn thông tin tra cứu."]
    )
    res = await execute_give_direct_answer(
        query="Key là gì?",
        context="Key là ma trận biểu diễn thông tin tra cứu.",
        model=fake_llm,
    )
    assert isinstance(res, GroundedAnswer)
    assert "Key" in res.answer


@pytest.mark.asyncio
async def test_tool_give_example():
    fake_llm = FakeListChatModel(responses=["Ví dụ về Key và Value trong từ điển."])
    res = await execute_give_example(
        concept="Key-Value",
        context="Cặp Key-Value hoạt động như từ điển.",
        model=fake_llm,
    )
    assert res.example != ""
    assert res.concept_mapping != ""


@pytest.mark.asyncio
async def test_tool_give_hint():
    fake_llm = FakeListChatModel(responses=["Hãy nghĩ về cách tra từ điển..."])
    res = await execute_give_hint(
        topic="Key",
        current_state="Học viên chưa phân biệt được Key và Value",
        model=fake_llm,
    )
    assert res.hint_level == 1
    assert res.hint != ""


@pytest.mark.asyncio
async def test_tool_motivate():
    fake_llm = FakeListChatModel(responses=["Đừng nản nhé, thử lại với bước nhỏ này."])
    res = await execute_motivate(
        difficulty="Nhầm lẫn giữa Key và Value",
        model=fake_llm,
    )
    assert res.acknowledged_difficulty != ""
    assert res.message != ""


@pytest.mark.asyncio
async def test_tool_validate_understanding_generate():
    fake_llm = FakeListChatModel(responses=["Multiple choice question..."])
    res = await execute_validate_understanding(
        mode="generate_check",
        context="Key dùng để so khớp với Query.",
        grounded_answer="Key dùng để so khớp.",
        model=fake_llm,
    )
    assert isinstance(res, MicroCheck)
    assert res.question != ""


@pytest.mark.asyncio
async def test_tool_validate_understanding_evaluate():
    fake_llm = FakeListChatModel(responses=["Evaluate answer..."])
    res = await execute_validate_understanding(
        mode="evaluate_answer",
        question="Key làm gì?",
        expected_answer="So khớp với Query",
        student_answer="So khớp với Query",
        context="Key dùng để so khớp.",
        model=fake_llm,
    )
    assert isinstance(res, CheckEvaluation)
    assert res.is_correct is True
