"""Backend settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class BackendSettings(BaseSettings):
    """Runtime configuration for the HTTP/application layers."""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "ai_core" / ".env"),
        env_file_encoding="utf-8",
        env_prefix="VLEARN_",
        extra="ignore",
    )

    environment: str = "development"
    api_title: str = "VLearn Adaptive Tutor Backend"
    api_version: str = "3.0.0"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )
    serve_frontend: bool = True
    anonymous_session_secret: str = "dev-only-change-me"
    session_cookie_name: str = "vlearn_session"
    session_cookie_secure: bool = False
    max_question_chars: int = Field(default=4000, ge=100, le=20000)
    max_selected_text_chars: int = Field(default=12000, ge=1000, le=50000)
    max_history_items: int = Field(default=50, ge=0, le=200)
    model_name: str = "gpt-5-nano"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_backend_settings() -> BackendSettings:
    return BackendSettings()
