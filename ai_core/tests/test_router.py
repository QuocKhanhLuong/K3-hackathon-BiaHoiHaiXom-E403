"""Unit tests for workflow router."""

import pytest
from vlearn_ai.graph.nodes import router_node


@pytest.mark.asyncio
async def test_router_simple_query():
    state = {
        "user_query": "Key là gì?",
        "selected_context": "Key trong Self-Attention được dùng để tính điểm so khớp với Query.",
        "tool_trace": [],
    }
    res = await router_node(state)
    assert res["route"] == "simple"


@pytest.mark.asyncio
async def test_router_clarify_query():
    state = {
        "user_query": "Cái này hoạt động như thế nào?",
        "selected_context": "",
        "tool_trace": [],
    }
    res = await router_node(state)
    assert res["route"] == "clarify"


@pytest.mark.asyncio
async def test_router_check_query():
    state = {
        "user_query": "Key và Value khác nhau như thế nào?",
        "selected_context": "Key dùng để so khớp với Query, Value chứa nội dung tổng hợp.",
        "tool_trace": [],
    }
    res = await router_node(state)
    assert res["route"] == "check"


@pytest.mark.asyncio
async def test_router_deep_query():
    state = {
        "user_query": "Tại sao attention phải chia cho căn bậc hai của d_k?",
        "selected_context": "Chia cho sqrt(d_k) để tránh gradient bị triệt tiêu khi d_k lớn.",
        "tool_trace": [],
    }
    res = await router_node(state)
    assert res["route"] == "deep"
