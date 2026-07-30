"""Configuration path regression tests."""

from pathlib import Path

from vlearn_ai.config import AI_CORE_DIR, Settings


def test_settings_include_package_local_env_file():
    configured_files = Settings.model_config["env_file"]
    assert Path(configured_files[-1]).resolve() == (AI_CORE_DIR / ".env").resolve()
