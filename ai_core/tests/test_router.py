"""Unit tests for router node classification."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.graph.nodes import router_node
from vlearn_ai.graph.state import LearningLoopState


@pytest.mark.asyncio
async def test_router_simple_query():
    fake_llm = DeterministicFakeChatModel(route_to_return="simple")
    state: LearningLoopState = {
        "user_query": "Key là gì?",
        "selected_context": "Key dùng để so khớp với Query.",
    }
    res = await router_node(state, model=fake_llm)
    assert res["route"] == "simple"
    assert res["route_confidence"] > 0.0


@pytest.mark.asyncio
async def test_router_clarify_query():
    fake_llm = DeterministicFakeChatModel(route_to_return="clarify")
    state: LearningLoopState = {
        "user_query": "Cái này hoạt động như thế nào?",
        "selected_context": "",
    }
    res = await router_node(state, model=fake_llm)
    assert res["route"] == "clarify"


@pytest.mark.asyncio
async def test_router_check_query():
    fake_llm = DeterministicFakeChatModel(route_to_return="check")
    state: LearningLoopState = {
        "user_query": "Key và Value khác nhau như thế nào?",
        "selected_context": "Key dùng để so khớp với Query, Value chứa nội dung.",
    }
    res = await router_node(state, model=fake_llm)
    assert res["route"] == "check"


@pytest.mark.asyncio
async def test_router_deep_query():
    fake_llm = DeterministicFakeChatModel(route_to_return="deep")
    state: LearningLoopState = {
        "user_query": "Tại sao attention phải chia cho căn d_k?",
        "selected_context": "Chia cho căn d_k để giảm độ lớn gradient.",
    }
    res = await router_node(state, model=fake_llm)
    assert res["route"] == "deep"
