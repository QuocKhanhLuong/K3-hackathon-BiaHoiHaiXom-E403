"""Unit tests for ask clarification workflow."""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from vlearn_ai.workflows.ask_clarification import run_ask_clarification

@pytest.mark.asyncio
async def test_ask_clarification_workflow():
    fake_llm = FakeListChatModel(responses=["Bạn có thể làm rõ hơn không?"])
    req = await run_ask_clarification(
        query="Cái này là gì?",
        context="",
        model=fake_llm,
    )
    assert req.clarification_question != ""
    assert req.reason != ""
