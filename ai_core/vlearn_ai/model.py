"""Factory module for OpenAI ChatOpenAI models with reasoning levels."""

import os
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from vlearn_ai.config import get_settings
from vlearn_ai.schemas import AIModelInvocationError


def _create_chat_model(
    reasoning_effort: Literal["minimal", "low", "medium", "high"],
) -> BaseChatModel:
    """Create ChatOpenAI instance with fixed gpt-5-nano model and given reasoning level."""
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        raise AIModelInvocationError(
            "OPENAI_API_KEY is not set. A valid OpenAI API key is required to instantiate real model."
        )

    kwargs = {
        "model": settings.OPENAI_MODEL,
        "api_key": api_key,
        "temperature": 0.0,
    }

    try:
        # Pass reasoning_effort if supported by ChatOpenAI version
        kwargs["reasoning_effort"] = reasoning_effort
        return ChatOpenAI(**kwargs)
    except (TypeError, ValueError):
        # Fallback without reasoning_effort if parameter is unsupported by installed version
        kwargs.pop("reasoning_effort", None)
        return ChatOpenAI(**kwargs)


def get_fast_model() -> BaseChatModel:
    """Get fast/control ChatOpenAI model (minimal reasoning effort)."""
    settings = get_settings()
    return _create_chat_model(settings.AI_FAST_REASONING)


def get_generation_model() -> BaseChatModel:
    """Get generation ChatOpenAI model (low reasoning effort)."""
    settings = get_settings()
    return _create_chat_model(settings.AI_GENERATION_REASONING)


def get_chat_model() -> BaseChatModel:
    """Default model getter backward-compatibility."""
    return get_fast_model()
