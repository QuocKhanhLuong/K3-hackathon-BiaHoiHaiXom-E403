"""Configuration settings for VLearn AI Core."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5-nano"
    AI_FAST_REASONING: str = "minimal"
    AI_GENERATION_REASONING: str = "low"
    AI_MAX_TOOL_STEPS: int = 4
    AI_MAX_RETRY_COUNT: int = 2
    AI_CONTEXT_MAX_CHARS: int = 12000


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
