"""Configuration centralisée — chargement depuis .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings


_PLACEHOLDER_SECRETS = {
    "",
    "sk-...",
    "sk-ant-...",
    "ntn_...",
}


def is_secret_configured(value: str) -> bool:
    """Return True only for non-placeholder secret values."""
    normalized = value.strip()
    if not normalized:
        return False
    if normalized in _PLACEHOLDER_SECRETS:
        return False
    if normalized.endswith("..."):
        return False
    return True


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # LLM API keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    mistral_api_key: str = ""

    # Notion
    notion_api_key: str = ""

    # Core API server
    core_host: str = "0.0.0.0"
    core_port: int = 8100

    # Authentication
    mascarade_api_key: str = ""

    # Defaults
    default_provider: str = "claude"
    default_model: str = "claude-sonnet-4-6"


settings = Settings()
