"""Optional real-model smoke test (only runs when OPENAI_API_KEY is present)."""

import os

import pytest
from vlearn_ai.config import get_settings
from vlearn_ai.interface import VLearnAICore
from vlearn_ai.model import get_chat_model
from vlearn_ai.schemas import RouteOutput


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Live OPENAI_API_KEY environment variable not provided",
)
@pytest.mark.asyncio
async def test_real_openai_gpt5_nano_model():
    cfg = get_settings()
    assert cfg.OPENAI_MODEL == "gpt-5-nano"

    model = get_chat_model(cfg)
    structured = model.with_structured_output(RouteOutput)

    res = await structured.ainvoke("Phân loại câu hỏi: Key là gì?")
    assert isinstance(res, RouteOutput)
    assert res.route in ("simple", "clarify", "check", "deep")

    ai_core = VLearnAICore(model=model)
    turn_res = await ai_core.start_turn(
        thread_id="smoke_test_real",
        question="Key là gì?",
        selected_context="Key trong Attention được dùng để tính điểm so khớp với Query.",
    )
    assert turn_res["status"] in (
        "completed",
        "awaiting_check",
        "awaiting_clarification",
    )
