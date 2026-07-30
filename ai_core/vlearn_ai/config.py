"""Configuration settings for VLearn AI Core package."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings for VLearn AI Core."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-5-nano")

    AI_FAST_REASONING: Literal["minimal", "low", "medium", "high"] = Field(
        default="minimal"
    )
    AI_GENERATION_REASONING: Literal["minimal", "low", "medium", "high"] = Field(
        default="low"
    )

    AI_MAX_TOOL_STEPS: int = Field(default=4, ge=1, le=10)
    AI_MAX_RETRY_COUNT: int = Field(default=2, ge=1, le=5)
    AI_CONTEXT_MAX_CHARS: int = Field(default=12000, ge=1000, le=50000)
    AI_RECURSION_LIMIT: int = Field(default=25, ge=5, le=100)

    @field_validator("OPENAI_MODEL")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if not v.startswith("gpt-5-nano"):
            raise ValueError("OPENAI_MODEL must start with 'gpt-5-nano'.")
        return v


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Get global settings instance singleton."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings() -> None:
    """Reset global settings singleton (useful for testing)."""
    global _settings_instance
    _settings_instance = None
