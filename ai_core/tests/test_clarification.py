"""Unit tests for ask clarification workflow."""

import pytest
from fake_model import DeterministicFakeChatModel
from vlearn_ai.workflows.ask_clarification import run_ask_clarification


@pytest.mark.asyncio
async def test_ask_clarification_workflow():
    fake_llm = DeterministicFakeChatModel()
    req = await run_ask_clarification(
        query="Cái này là gì?",
        context="",
        model=fake_llm,
    )
    assert req.clarification_question != ""
    assert req.reason != ""
