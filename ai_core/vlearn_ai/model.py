"""OpenAI model factory providing configured gpt-5-nano instances."""

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from vlearn_ai.config import get_settings
from vlearn_ai.schemas import AIModelInvocationError


def create_vlearn_model(
    reasoning_effort: Literal["minimal", "low", "medium", "high"] = "minimal",
    temperature: float = 0.0,
) -> BaseChatModel:
    """Create a ChatOpenAI model instance configured for gpt-5-nano with explicit reasoning effort."""
    settings = get_settings()

    api_key = settings.OPENAI_API_KEY
    model_name = settings.OPENAI_MODEL

    if not model_name.startswith("gpt-5-nano"):
        raise ValueError(
            f"Invalid model '{model_name}'. VLearn AI Core strictly requires 'gpt-5-nano'."
        )

    try:
        # Instantiate ChatOpenAI with explicit reasoning_effort
        return ChatOpenAI(
            model=model_name,
            api_key=api_key or "fake-api-key-for-testing",  # type: ignore
            temperature=temperature,
            reasoning_effort=reasoning_effort,  # type: ignore
        )
    except TypeError as exc:
        raise AIModelInvocationError(
            "Installed langchain-openai does not support required reasoning configuration."
        ) from exc


def get_fast_model() -> BaseChatModel:
    """Get fast model instance for control, guards, and router nodes."""
    settings = get_settings()
    return create_vlearn_model(
        reasoning_effort=settings.AI_FAST_REASONING,
        temperature=0.0,
    )


def get_generation_model() -> BaseChatModel:
    """Get generation model instance for pedagogical tools, check generation, and repair nodes."""
    settings = get_settings()
    return create_vlearn_model(
        reasoning_effort=settings.AI_GENERATION_REASONING,
        temperature=0.0,
    )
