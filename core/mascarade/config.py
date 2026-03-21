"""Configuration centralisée — chargement depuis .env."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

_PLACEHOLDER_SECRETS = {
    "",
    "sk-...",
    "sk-ant-...",
}


def is_secret_configured(value: str | SecretStr) -> bool:
    """Return True only for non-placeholder secret values."""
    # Handle SecretStr type
    if isinstance(value, SecretStr):
        value = value.get_secret_value()

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
    anthropic_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    openai_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    mistral_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    google_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    google_auth_mode: str = "api_key"
    huggingface_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    huggingface_auth_mode: str = "api_key"
    huggingface_base_url: str = "https://router.huggingface.co/v1"
    huggingface_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    huggingface_oauth_access_token: SecretStr = Field(default=SecretStr(""), repr=False)
    huggingface_oauth_refresh_token: SecretStr = Field(default=SecretStr(""), repr=False)
    huggingface_oauth_client_id: SecretStr = Field(default=SecretStr(""), repr=False)
    huggingface_oauth_client_secret: SecretStr = Field(default=SecretStr(""), repr=False)
    huggingface_oauth_token_endpoint: str = "https://huggingface.co/oauth/token"
    huggingface_oauth_expires_at: str = ""

    # AWS Bedrock
    aws_access_key_id: SecretStr = Field(default=SecretStr(""), repr=False)
    aws_secret_access_key: SecretStr = Field(default=SecretStr(""), repr=False)
    aws_session_token: SecretStr = Field(default=SecretStr(""), repr=False)
    aws_region: str = "eu-west-1"
    aws_bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # AWS Secrets Manager integration
    use_aws_secrets: bool = False
    aws_secret_name: str = ""
    aws_secrets_region: str = "eu-west-1"

    # Google / Gemini
    google_oauth_access_token: SecretStr = Field(default=SecretStr(""), repr=False)
    google_oauth_refresh_token: SecretStr = Field(default=SecretStr(""), repr=False)
    google_oauth_client_id: SecretStr = Field(default=SecretStr(""), repr=False)
    google_oauth_client_secret: SecretStr = Field(default=SecretStr(""), repr=False)
    google_oauth_token_endpoint: str = "https://oauth2.googleapis.com/token"
    google_oauth_expires_at: str = ""
    google_cloud_project: str = ""
    google_cloud_location: str = "europe-west1"
    google_application_credentials: SecretStr = Field(default=SecretStr(""), repr=False)
    google_model: str = "gemini-2.5-flash"

    # Knowledge base provider
    knowledge_base_provider: str = "memos"
    knowledge_base_smoke_page_id: str = ""
    memos_base_url: str = ""
    memos_public_url: str = ""
    memos_access_token: SecretStr = Field(default=SecretStr(""), repr=False)
    memos_default_visibility: str = "PRIVATE"
    docmost_base_url: str = ""
    docmost_email: str = ""
    docmost_password: SecretStr = Field(default=SecretStr(""), repr=False)
    docmost_space_id: str = ""

    # GitHub dispatch
    github_dispatch_auth_mode: str = "token"
    github_app_id: str = ""
    github_app_private_key: SecretStr = Field(default=SecretStr(""), repr=False)
    github_app_installation_id: str = ""

    # Ollama
    ollama_enabled: bool = False
    ollama_base_url: str = "http://ollama:11434"
    ollama_timeout_seconds: float = 180.0

    # llama.cpp (OpenAI-compatible local server)
    llama_cpp_enabled: bool = False
    llama_cpp_base_url: str = "http://localhost:8081/v1"
    llama_cpp_timeout_seconds: float = 120.0

    # MLX-LM (Apple Silicon native inference via mlx-lm server)
    mlx_lm_enabled: bool = False
    mlx_lm_base_url: str = "http://localhost:8201"
    mlx_lm_default_model: str = "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
    mlx_lm_timeout_seconds: float = 120.0

    # Apple Silicon local LLM service
    apple_llm_enabled: bool = False
    apple_llm_base_url: str = "http://apple-llm:8201"
    apple_llm_model_id: str = "apple-local"
    apple_llm_backend: str = "coreml"
    apple_llm_timeout_seconds: float = 300.0
    apple_llm_models_json: str = ""

    # ComfyUI
    comfyui_url: str = ""

    # Database
    database_url: SecretStr = Field(
        default=SecretStr("postgresql://mascarade:mascarade@postgres:5432/mascarade"),
        repr=False,
    )
    # Qdrant
    qdrant_url: str = "http://qdrant:6333"

    # Core API server
    core_host: str = "0.0.0.0"
    core_port: int = 8100

    # Authentication
    mascarade_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    cluster_enabled: bool = False
    cluster_shared_key: SecretStr = Field(default=SecretStr(""), repr=False)

    # Cluster / multi-node
    node_id: str = "node-1"
    node_role: str = "general"
    node_label: str = "Mascarade Node 1"
    mesh_bind_host: str = ""
    mesh_scheme: str = "http"
    cluster_request_timeout_ms: int = 5000
    cluster_heartbeat_seconds: int = 30
    cluster_forward_enabled: bool = True
    cluster_require_tls: bool = True
    cluster_allow_insecure_loopback: bool = False
    cluster_peers: str = ""
    cluster_mdns_enabled: bool = False
    cluster_mdns_service: str = "_mascarade._tcp.local."
    cluster_mdns_discovery_ttl_seconds: int = 60
    cluster_mdns_advertise: bool = False

    # Distributed scheduler
    scheduler_enabled: bool = False
    scheduler_workers: str = ""  # comma-separated: "kxkm-ai:8201,tower:8201,grosmac:8201"
    scheduler_heartbeat_interval: int = 5  # seconds
    scheduler_max_queue: int = 200
    scheduler_max_wait_s: int = 30

    # P2P network
    p2p_enabled: bool = False
    p2p_listen_host: str = "0.0.0.0"
    p2p_listen_port: int = 4001
    p2p_bootstrap_peers: str = ""  # libp2p: multiaddr; asyncio: "peer_id|host|port"
    p2p_key_dir: str = ""
    p2p_identity_key_path: str = ""
    p2p_heartbeat_interval_seconds: int = 15
    p2p_heartbeat_seconds: int = 30
    p2p_discovery_interval_seconds: int = 30
    p2p_peer_ttl_seconds: int = 90
    p2p_pubsub_enabled: bool = False
    p2p_require_signatures: bool = True
    # Device voice sessions
    device_stt_model: str = "gpt-4o-mini-transcribe"
    device_stt_language: str = "fr"
    device_tts_model: str = "gpt-4o-mini-tts"
    device_tts_voice: str = "sage"
    device_voice_max_audio_bytes: int = 2_000_000
    device_reply_ttl_seconds: int = 900

    # Observability
    otel_enabled: bool = False
    otel_collector_http_endpoint: str = "http://otel-collector:4318"
    ops_agent_url: str = "http://ops-agent:9200"
    loki_url: str = "http://loki:3100"

    # ClickHouse
    clickhouse_host: str = "http://clickhouse:8123"
    clickhouse_user: str = "langfuse"
    clickhouse_password: SecretStr = Field(default=SecretStr(""), repr=False)
    clickhouse_database: str = "default"

    # Mistral Studio
    mistral_api_base: str = "https://api.mistral.ai/v1"
    mistral_default_model: str = "mistral-large-latest"
    mistral_timeout_ms: int = 120000
    litellm_proxy_enabled: bool = False
    litellm_base_url: str = "http://litellm:4000"
    litellm_master_key: SecretStr = Field(default=SecretStr(""), repr=False)
    routellm_enabled: bool = False
    routellm_threshold: float = 0.58
    routellm_cheap_provider: str = "openai"
    routellm_cheap_model: str = "gpt-4o-mini"
    routellm_strong_provider: str = "openai"
    routellm_strong_model: str = "gpt-4.1"
    orchestrator_ray_enabled: bool = False
    orchestrator_ray_address: str = "auto"
    orchestrator_ray_namespace: str = "mascarade"

    # Orchestrator retry settings
    orchestrator_default_max_retries: int = 3
    orchestrator_default_backoff_seconds: float = 1.0
    orchestrator_default_max_backoff_seconds: float = 60.0
    orchestrator_default_backoff_multiplier: float = 2.0

    # Circuit breaker settings
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_success_threshold: int = 2
    circuit_breaker_timeout_seconds: float = 60.0

    # Dead letter queue settings
    dead_letter_max_entries: int = 1000
    dead_letter_retention_seconds: int = 86400

    # Defaults
    default_provider: str = "claude"
    default_model: str = "claude-sonnet-4-6"

    # Domain-aware routing
    domain_model_mappings: str = ""
    use_ml_classifier: bool = False  # Enable ML classifier for domain detection


settings = Settings()
