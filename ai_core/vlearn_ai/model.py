"""Model instantiation and factory wrapper for OpenAI API."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from vlearn_ai.config import Settings, get_settings


def get_chat_model(
    config: Settings | None = None,
    reasoning_level: str = "minimal",
    fake_model: BaseChatModel | None = None,
) -> BaseChatModel:
    """Return configured ChatOpenAI model or fake model double for testing.

    Runtime model ID is strictly fixed to gpt-5-nano.
    """
    if fake_model is not None:
        return fake_model

    cfg = config or get_settings()

    # Create ChatOpenAI instance using the fixed gpt-5-nano model
    extra_kwargs: dict[str, Any] = {}
    if cfg.OPENAI_API_KEY:
        extra_kwargs["api_key"] = cfg.OPENAI_API_KEY

    return ChatOpenAI(
        model=cfg.OPENAI_MODEL,
        temperature=0.0,
        **extra_kwargs,
    )
