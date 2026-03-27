"""Configuration centralisée — chargement depuis .env."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

_PLACEHOLDER_SECRETS = {
    "",
    "sk-...",
    "sk-ant-...",
}


def secret_value(value: str | SecretStr) -> str:
    """Return the plain string value for either a raw string or SecretStr."""
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


def is_secret_configured(value: str | SecretStr) -> bool:
    """Return True only for non-placeholder secret values."""
    value = secret_value(value)
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
    github_copilot_token: SecretStr = Field(default=SecretStr(""), repr=False)
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
    mascarade_project_id: str = "default"
    knowledge_base_smoke_page_id: str = ""
    memos_base_url: str = ""
    memos_public_url: str = ""
    memos_access_token: SecretStr = Field(default=SecretStr(""), repr=False)
    memos_default_visibility: str = "PRIVATE"
    docmost_base_url: str = ""
    docmost_email: str = ""
    docmost_password: SecretStr = Field(default=SecretStr(""), repr=False)
    docmost_space_id: str = ""
    kxkm_rag_url: str = "http://localhost:3333"
    kxkm_timeout_seconds: float = 20.0
    kxkm_dpo_persona: str = "pharmacius"

    # GitHub dispatch
    github_dispatch_auth_mode: str = "token"
    github_app_id: str = ""
    github_app_private_key: SecretStr = Field(default=SecretStr(""), repr=False)
    github_app_installation_id: str = ""

    # Perplexity (sonar models with built-in web search)
    perplexity_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    perplexity_base_url: str = "https://api.perplexity.ai"

    # Codestral (Mistral code model — FIM + chat)
    codestral_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    codestral_timeout_seconds: float = 120.0

    # Ollama
    ollama_enabled: bool = False
    ollama_base_url: str = "http://ollama:11434"
    ollama_timeout_seconds: float = 180.0

    # Exo (distributed inference cluster, OpenAI-compatible)
    exo_enabled: bool = False
    exo_base_url: str = "http://localhost:52415"
    exo_timeout_seconds: float = 120.0

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

    # Apple Foundation Models (on-device 3B via Swift bridge)
    afm_enabled: bool = False
    afm_bridge_url: str = "http://localhost:8090"
    afm_default_model: str = "apple-fm-3b"
    afm_timeout_seconds: float = 60.0
    afm_bridge_path: str = "/usr/local/bin/afm-bridge"

    # ComfyUI
    comfyui_url: str = ""

    # Database
    database_url: SecretStr = Field(
        default=SecretStr("postgresql://mascarade:mascarade@postgres:5432/mascarade"),
        repr=False,
    )
    # Qdrant
    qdrant_url: str = "http://qdrant:6333"

    # LightRAG (graph-augmented RAG via lightrag-hku)
    lightrag_enabled: bool = False
    lightrag_working_dir: str = "/tmp/mascarade_lightrag"
    lightrag_extraction_model: str = "mistral:7b"  # Ollama model for entity extraction

    # RAG pipeline
    rag_reranker_enabled: bool = True
    rag_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    # Contextual Retrieval (Anthropic pattern) — opt-in: adds ~1 LLM call/chunk at indexation
    rag_contextual_retrieval_enabled: bool = False
    # Use "provider/model" syntax to force a specific provider, e.g. "anthropic/claude-haiku-4-5-20251001"
    rag_contextual_retrieval_model: str = "claude-haiku-4-5-20251001"
    # Semantic query cache (Redis + Qdrant) — reduces redundant LLM calls by 50-70%
    rag_cache_enabled: bool = False  # opt-in: requires Redis
    rag_cache_similarity_threshold: float = 0.92
    rag_cache_ttl: int = 3600  # seconds
    # Embedding provider override (default "auto" = OpenAI→Mistral→HF→Ollama→fastembed)
    # Set "ollama" + rag_embedding_model="bge-m3:latest" for best self-hosted quality
    rag_embedding_provider: str = "auto"
    rag_embedding_model: str = ""  # empty = provider default
    # Chunking (used by ingest/url and ingest/upload endpoints)
    rag_chunk_size: int = 512  # target tokens per chunk
    rag_chunk_overlap: int = 50  # token overlap between adjacent chunks

    # Core API server
    core_host: str = "0.0.0.0"
    core_port: int = 8100
    cors_allowed_origins: str = ""

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

    # Auto-scaling configuration
    autoscaling_enabled: bool = False  # Enable auto-scaling
    autoscaling_min_workers: int = 1  # Minimum number of workers
    autoscaling_max_workers: int = 10  # Maximum number of workers
    autoscaling_scale_up_cpu_threshold: float = 0.7  # CPU usage threshold for scale-up
    autoscaling_scale_down_cpu_threshold: float = 0.3  # CPU usage threshold for scale-down
    autoscaling_scale_up_memory_threshold: float = 0.8  # Memory usage threshold for scale-up
    autoscaling_scale_down_memory_threshold: float = 0.4  # Memory usage threshold for scale-down
    autoscaling_scale_up_queue_threshold: int = 50  # Queue depth threshold for scale-up
    autoscaling_scale_down_queue_threshold: int = 10  # Queue depth threshold for scale-down
    autoscaling_cooldown_seconds: int = 300  # Cooldown period between scaling operations

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
    # P2P as LLM provider (route requests to peers)
    p2p_provider_enabled: bool = False
    p2p_provider_timeout_seconds: float = 120.0
    # Fake Ollama server (Ollama-compatible API backed by router)
    fake_ollama_enabled: bool = False
    fake_ollama_port: int = 11434
    fake_ollama_host: str = "0.0.0.0"
    # GitHub Copilot (via copilot-api sidecar proxy)
    github_copilot_proxy_url: str = "http://localhost:4141"
    github_copilot_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    # Device voice sessions
    device_stt_model: str = "gpt-4o-mini-transcribe"
    device_stt_language: str = "fr"
    device_tts_model: str = "gpt-4o-mini-tts"
    device_tts_voice: str = "sage"
    device_voice_max_audio_bytes: int = 2_000_000
    device_reply_ttl_seconds: int = 900

    # Voice pipeline (OPUS -> VAD -> ASR -> LLM -> TTS)
    voice_pipeline_enabled: bool = True

    # faster-whisper local STT (optional dep: pip install mascarade-core[voice])
    whisper_model_size: str = "base"  # tiny / base / small / medium / large-v3
    whisper_device: str = "auto"  # auto / cpu / cuda
    whisper_compute_type: str = "int8"  # int8 / float16 / float32

    # Voice bridge (ESP32 WebSocket pipeline)
    voice_bridge_tts_url: str = (
        "http://192.168.0.120:8001/v1/audio/speech"  # override: VOICE_BRIDGE_TTS_URL
    )
    voice_bridge_tts_voice: str = "alloy"  # override: VOICE_BRIDGE_TTS_VOICE

    # Observability
    openllmetry_enabled: bool = False
    otel_enabled: bool = False
    otel_collector_http_endpoint: str = "http://otel-collector:4318"
    otel_exporter_protocol: str = "http/protobuf"  # or "grpc"
    otel_exporter_headers: str = ""  # "Authorization=Bearer token"
    otel_service_name: str = "mascarade-core"
    otel_resource_attributes: str = ""  # "team.id=core,deployment=production"
    ops_agent_url: str = "http://ops-agent:9200"
    loki_url: str = "http://loki:3100"

    # Langfuse (self-hosted tracing)
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = Field(default=SecretStr(""), repr=False)
    langfuse_host: str = "http://langfuse-web:3000"
    langfuse_init_project_public_key: str = ""
    langfuse_init_project_secret_key: SecretStr = Field(default=SecretStr(""), repr=False)

    # ClickHouse
    clickhouse_host: str = "http://clickhouse:8123"
    clickhouse_user: str = "langfuse"
    clickhouse_password: SecretStr = Field(default=SecretStr(""), repr=False)
    clickhouse_database: str = "default"

    # Mistral Studio
    mistral_api_base: str = "https://api.mistral.ai/v1"
    mistral_default_model: str = "mistral-large-latest"
    mistral_timeout_ms: int = 120000
    mistral_agents_api_mode: str = "beta"
    mistral_agent_sentinelle_id: str = ""
    mistral_agent_tower_id: str = ""
    mistral_agent_forge_id: str = ""
    mistral_agent_devstral_id: str = ""
    litellm_proxy_enabled: bool = False
    litellm_enabled: bool = False
    litellm_base_url: str = "http://litellm:4000"
    litellm_master_key: SecretStr = Field(default=SecretStr(""), repr=False)
    litellm_timeout_seconds: float = 120.0
    litellm_universal_enabled: bool = False
    litellm_universal_default_model: str = "gpt-4o"
    routellm_enabled: bool = False
    routellm_threshold: float = 0.58
    routellm_cheap_provider: str = "ollama"
    routellm_cheap_model: str = "qwen3.5:9b"
    routellm_strong_provider: str = "claude"
    routellm_strong_model: str = "claude-sonnet-4-6"
    orchestrator_ray_enabled: bool = False
    orchestrator_ray_address: str = "auto"
    orchestrator_ray_namespace: str = "mascarade"

    # Eval harness (lm-evaluation-harness integration)
    eval_harness_enabled: bool = False
    eval_harness_cache_dir: str = "data/eval_cache"

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

    # A2A (Agent-to-Agent) protocol — spec v0.3
    a2a_enabled: bool = False
    a2a_agent_name: str = "mascarade"
    a2a_agent_url: str = ""
    a2a_auth_method: str = "bearer"  # bearer | oauth2

    # Machine profile (hardware-aware routing)
    machine_profile_enabled: bool = True
    machine_profile_override: str = ""  # force: "apple_m4", "nvidia_4090", "cpu_only"

    # Defaults
    default_provider: str = "claude"
    default_model: str = "claude-sonnet-4-6"

    # Domain-aware routing
    domain_model_mappings: str = ""
    use_ml_classifier: bool = False  # Enable ML classifier for domain detection
    use_bert_classifier: bool = False  # Enable BERT classifier for domain detection

    # ML routing classifier (tier prediction: strong/cheap/fast)
    ml_routing_classifier_enabled: bool = False
    ml_routing_classifier_path: str = ""  # Path to model JSON; empty = default ~/.mascarade/models/

    # Multi-tier cache configuration
    cache_enabled: bool = True  # Enable multi-tier caching
    cache_l1_size: int = 1000  # In-memory cache size
    cache_l2_enabled: bool = False  # Enable Redis cache (L2)
    cache_l2_host: str = "localhost"  # Redis host
    cache_l2_port: int = 6379  # Redis port
    cache_l2_password: SecretStr = Field(default=SecretStr(""), repr=False)  # Redis password
    cache_l2_db: int = 0  # Redis database
    cache_l3_enabled: bool = False  # Enable semantic cache (L3)
    cache_l3_similarity_threshold: float = 0.85  # Similarity threshold for semantic cache


settings = Settings()
