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
    google_api_key: str = ""
    huggingface_api_key: str = ""
    huggingface_auth_mode: str = "api_key"
    huggingface_base_url: str = "https://router.huggingface.co/v1"
    huggingface_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    huggingface_oauth_access_token: str = ""
    huggingface_oauth_refresh_token: str = ""
    huggingface_oauth_client_id: str = ""
    huggingface_oauth_client_secret: str = ""
    huggingface_oauth_token_endpoint: str = "https://huggingface.co/oauth/token"
    huggingface_oauth_expires_at: str = ""

    # AWS Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_region: str = "eu-west-1"
    aws_bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # Google / Gemini
    google_cloud_project: str = ""
    google_cloud_location: str = "europe-west1"
    google_application_credentials: str = ""
    google_model: str = "gemini-2.5-flash"

    # Notion
    notion_auth_mode: str = "api_key"
    notion_api_key: str = ""
    notion_oauth_access_token: str = ""
    notion_oauth_refresh_token: str = ""
    notion_oauth_client_id: str = ""
    notion_oauth_client_secret: str = ""
    notion_oauth_authorization_endpoint: str = "https://api.notion.com/v1/oauth/authorize"
    notion_oauth_token_endpoint: str = "https://api.notion.com/v1/oauth/token"
    notion_oauth_redirect_uri: str = ""
    notion_oauth_expires_at: str = ""
    notion_oauth_workspace_name: str = ""

    # GitHub dispatch
    github_dispatch_auth_mode: str = "token"
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_installation_id: str = ""

    # Ollama
    ollama_enabled: bool = False
    ollama_base_url: str = "http://ollama:11434"

    # Apple Silicon local LLM service
    apple_llm_enabled: bool = False
    apple_llm_base_url: str = "http://apple-llm:8201"
    apple_llm_model_id: str = "apple-local"
    apple_llm_backend: str = "coreml"
    apple_llm_timeout_seconds: float = 300.0

    # ComfyUI
    comfyui_url: str = ""

    # Core API server
    core_host: str = "0.0.0.0"
    core_port: int = 8100

    # Authentication
    mascarade_api_key: str = ""
    cluster_enabled: bool = False
    cluster_shared_key: str = ""

    # Cluster / multi-node
    node_id: str = "node-1"
    node_role: str = "general"
    node_label: str = "Mascarade Node 1"
    mesh_bind_host: str = ""
    mesh_scheme: str = "http"
    cluster_request_timeout_ms: int = 5000
    cluster_heartbeat_seconds: int = 30
    cluster_forward_enabled: bool = True
    cluster_peers: str = ""

    # Observability
    otel_enabled: bool = False
    otel_collector_http_endpoint: str = "http://otel-collector:4318"
    ops_agent_url: str = "http://ops-agent:9200"
    loki_url: str = "http://loki:3100"

    # Mistral Studio
    mistral_api_base: str = "https://api.mistral.ai/v1"
    mistral_default_model: str = "mistral-large-latest"
    mistral_timeout_ms: int = 120000

    # Defaults
    default_provider: str = "claude"
    default_model: str = "claude-sonnet-4-6"


settings = Settings()
