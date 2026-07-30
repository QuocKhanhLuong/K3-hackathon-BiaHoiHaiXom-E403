"""Opt-in live integration tests calling real OpenAI gpt-5-nano model."""

import os

import pytest
from vlearn_ai.config import get_settings
from vlearn_ai.model import get_fast_model


@pytest.mark.live
@pytest.mark.asyncio
async def test_real_openai_gpt5_nano_model():
    """Opt-in live test for real OpenAI gpt-5-nano model integration."""
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        pytest.skip("Skipping live model test because OPENAI_API_KEY is not set.")

    model = get_fast_model()
    res = await model.ainvoke("Xin chào, trả lời 1 từ 'OK' nếu bạn hoạt động.")
    content = res.content if hasattr(res, "content") else str(res)
    assert len(str(content).strip()) > 0
