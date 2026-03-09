#!/usr/bin/env bash
# scripts/compose.sh — Generation du docker-compose.yml

generate_compose() {
    local output="${1:-$REPO_DIR/docker-compose.yml}"
    local volumes_output=""
    local id func

    # Charger tous les modules
    for mod_file in "$REPO_DIR/scripts/modules/"*.sh; do
        # shellcheck disable=SC1090
        source "$mod_file"
    done

    {
        # Header
        cat <<'HEADER'
# docker-compose.yml — Genere par Mascarade setup
# Ne pas editer manuellement, utiliser ./config pour reconfigurer

services:
HEADER

        # Services selectionnes
        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" != "1" ]] && continue
            local func="module_${id//-/_}_compose"
            if declare -f "$func" &>/dev/null; then
                "$func"
                echo ""
            fi
        done

        # Networks
        cat <<'NETWORKS'
networks:
  mascarade-network:
    driver: bridge
NETWORKS

        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" != "1" ]] && continue
            func="module_${id//-/_}_volumes"
            if declare -f "$func" &>/dev/null; then
                volumes_output+="$("$func")"
                if [[ -n "${volumes_output}" && "${volumes_output: -1}" != $'\n' ]]; then
                    volumes_output+=$'\n'
                fi
            fi
        done

        if [[ -n "${volumes_output//[[:space:]]/}" ]]; then
            echo ""
            echo "volumes:"
            printf "%s" "$volumes_output"
        fi

    } > "$output"
}

# ── Collecte de la configuration .env de tous les modules ──
collect_module_configs() {
    for mod_file in "$REPO_DIR/scripts/modules/"*.sh; do
        # shellcheck disable=SC1090
        source "$mod_file"
    done

    for id in "${SVC_IDS[@]}"; do
        [[ "${SVC_ON[$id]}" != "1" ]] && continue
        local func="module_${id//-/_}_config"
        if declare -f "$func" &>/dev/null; then
            local label="${SVC_LABEL[$id]}"
            echo ""
            log "Configuration ${label}..."
            "$func"
        fi
    done
}

# ── Ecriture du fichier .env ──
write_env_file() {
    local env_file="${1:-$REPO_DIR/.env}"
    _rand_secret() {
        local bytes="${1:-24}"
        openssl rand -hex "$bytes" 2>/dev/null || head -c $((bytes * 2)) /dev/urandom | od -An -tx1 | tr -d ' \n'
    }
    local default_postgres_password="${POSTGRES_PASSWORD:-$(_rand_secret 24)}"
    local default_clickhouse_password="${CLICKHOUSE_PASSWORD:-$(_rand_secret 24)}"
    local default_minio_root_password="${MINIO_ROOT_PASSWORD:-$(_rand_secret 24)}"

    # Backup si existant
    backup_file "$env_file"

    {
        echo "# .env — Genere par Mascarade setup — $(date '+%Y-%m-%d %H:%M')"
        echo ""
        echo "# ── Images Docker (surchargables) ──"
        echo "LITELLM_IMAGE=\"${LITELLM_IMAGE:-ghcr.io/berriai/litellm@sha256:59a2736ac84800821fa0e1656487366089f2d29d10f8ae05c918df9c6e4940af}\""
        echo "N8N_IMAGE=\"${N8N_IMAGE:-n8nio/n8n@sha256:cfa50544c4cc172506834da1ec9bb5171db55958c8d1918205df0bda237a56f4}\""
        echo "LANGFUSE_WORKER_IMAGE=\"${LANGFUSE_WORKER_IMAGE:-langfuse/langfuse-worker@sha256:8bb47a4240ea293a210e460eae912ce06ea8fc2f724ce89cb146547eed36f6b2}\""
        echo "LANGFUSE_WEB_IMAGE=\"${LANGFUSE_WEB_IMAGE:-langfuse/langfuse@sha256:8d3211972d2a0610258ff0cc86da6b2d367f804bf253e9b94863bf961e59d23c}\""
        echo "FIRECRAWL_IMAGE=\"${FIRECRAWL_IMAGE:-mcp/firecrawl@sha256:e6676bd31d1806574d931b7a7b7b6fba953c031853e80adc1ec8115c17ab81ca}\""
        echo "MEM0_IMAGE=\"${MEM0_IMAGE:-mem0/openmemory-mcp:latest}\""
        echo "TEMPO_IMAGE=\"${TEMPO_IMAGE:-grafana/tempo:latest}\""
        echo "MINIO_IMAGE=\"${MINIO_IMAGE:-minio/minio@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e}\""
        echo "DIFY_API_IMAGE=\"${DIFY_API_IMAGE:-langgenius/dify-api@sha256:5f622b4d0b39bdc6d3b401063cfb60962fa92dcc63f55daccec138f98b260e67}\""
        echo "DIFY_WEB_IMAGE=\"${DIFY_WEB_IMAGE:-langgenius/dify-web@sha256:30339b4d5060488fac147ddc6fb40438ef71cd5f5dfdeb26c886768302bf7197}\""
        echo "CLICKHOUSE_IMAGE=\"${CLICKHOUSE_IMAGE:-clickhouse/clickhouse-server@sha256:0b2d7824347397b2ba6fcb216f0ae772568105f1f47e19f0d3247e24c79bc10a}\""
        echo "OLLAMA_IMAGE=\"${OLLAMA_IMAGE:-ollama/ollama@sha256:719122581b6932e1240ae70d788859089cb80d17e23cd4f98ba960b0290f70cb}\""
        echo "REDIS_IMAGE=\"${REDIS_IMAGE:-redis@sha256:8b81dd37ff027bec4e516d41acfbe9fe2460070dc6d4a4570a2ac5b9d59df065}\""
        echo "POSTGRES_IMAGE=\"${POSTGRES_IMAGE:-postgres@sha256:20edbde7749f822887a1a022ad526fde0a47d6b2be9a8364433605cf65099416}\""
        echo "QDRANT_IMAGE=\"${QDRANT_IMAGE:-qdrant/qdrant@sha256:f1c7272cdac52b38c1a0e89313922d940ba50afd90d593a1605dbbc214e66ffb}\""
        echo "GRAFANA_IMAGE=\"${GRAFANA_IMAGE:-grafana/grafana@sha256:b0ae311af06228bcfd4a620504b653db80f5b91e94dc3dc2a5b7dab202bcde20}\""
        echo "PROMETHEUS_IMAGE=\"${PROMETHEUS_IMAGE:-prom/prometheus@sha256:4a61322ac1103a0e3aea2a61ef1718422a48fa046441f299d71e660a3bc71ae9}\""
        echo "BLACKBOX_EXPORTER_IMAGE=\"${BLACKBOX_EXPORTER_IMAGE:-prom/blackbox-exporter:latest}\""
        echo "LOKI_IMAGE=\"${LOKI_IMAGE:-grafana/loki:3.5.3}\""
        echo "PROMTAIL_IMAGE=\"${PROMTAIL_IMAGE:-grafana/promtail:3.5.3}\""
        echo "OTEL_COLLECTOR_IMAGE=\"${OTEL_COLLECTOR_IMAGE:-otel/opentelemetry-collector-contrib:0.116.1}\""
        echo "COMFYUI_IMAGE=\"${COMFYUI_IMAGE:-comfyanonymous/comfyui:latest}\""
        echo "STT_IMAGE=\"${STT_IMAGE:-onerahmet/openai-whisper-asr-webservice:latest}\""
        echo "GENERATE_AUDIO_IMAGE=\"${GENERATE_AUDIO_IMAGE:-}\""
        echo "TTS_PIPER_IMAGE=\"${TTS_PIPER_IMAGE:-rhasspy/wyoming-piper:latest}\""
        echo "TTS_KOKORO_IMAGE=\"${TTS_KOKORO_IMAGE:-ghcr.io/marjocchi/wyoming-kokoro:latest}\""
        echo ""
        echo "# ── Publication reseau ──"
        echo "PUBLISH_BIND_HOST=\"${PUBLISH_BIND_HOST:-127.0.0.1}\""
        echo ""

        # Core
        if svc_selected "core"; then
            echo "# ── Mascarade Core ──"
            echo "CORE_PORT=\"${CORE_PORT:-8100}\""
            echo "CORE_HOST=\"${CORE_HOST:-0.0.0.0}\""
            echo "AGENT_FACTORY_COCKPIT_DIR=\"${AGENT_FACTORY_COCKPIT_DIR:-/workspace/agent-factory-cockpit}\""
            echo "DEFAULT_PROVIDER=\"${DEFAULT_PROVIDER:-claude}\""
            echo "DEFAULT_MODEL=\"${DEFAULT_MODEL:-claude-sonnet-4-6}\""
            echo "OLLAMA_BASE_URL=\"${OLLAMA_BASE_URL:-http://ollama:11434}\""
            echo "MASCARADE_API_KEY=\"${MASCARADE_API_KEY:-}\""
            echo "CLUSTER_ENABLED=\"${CLUSTER_ENABLED:-false}\""
            echo "NODE_ID=\"${NODE_ID:-node-1}\""
            echo "NODE_ROLE=\"${NODE_ROLE:-general}\""
            echo "NODE_LABEL=\"${NODE_LABEL:-Mascarade Node 1}\""
            echo "MESH_BIND_HOST=\"${MESH_BIND_HOST:-}\""
            echo "MESH_SCHEME=\"${MESH_SCHEME:-http}\""
            echo "CLUSTER_SHARED_KEY=\"${CLUSTER_SHARED_KEY:-}\""
            echo "CLUSTER_REQUEST_TIMEOUT_MS=\"${CLUSTER_REQUEST_TIMEOUT_MS:-5000}\""
            echo "CLUSTER_HEARTBEAT_SECONDS=\"${CLUSTER_HEARTBEAT_SECONDS:-30}\""
            echo "CLUSTER_FORWARD_ENABLED=\"${CLUSTER_FORWARD_ENABLED:-true}\""
            echo "CLUSTER_PEERS=\"${CLUSTER_PEERS:-}\""
            echo "DEFAULT_LLM_PROVIDER=\"${DEFAULT_LLM_PROVIDER:-anthropic}\""
            echo "DEFAULT_LLM_MODEL=\"${DEFAULT_LLM_MODEL:-claude-sonnet-4-20250514}\""
            echo ""
            echo "# ── Cles API LLM ──"
            [[ -n "${ANTHROPIC_API_KEY:-}" ]] && echo "ANTHROPIC_API_KEY=\"$ANTHROPIC_API_KEY\""
            [[ -n "${OPENAI_API_KEY:-}" ]] && echo "OPENAI_API_KEY=\"$OPENAI_API_KEY\""
            [[ -n "${GOOGLE_API_KEY:-}" ]] && echo "GOOGLE_API_KEY=\"$GOOGLE_API_KEY\""
            [[ -n "${MISTRAL_API_KEY:-}" ]] && echo "MISTRAL_API_KEY=\"$MISTRAL_API_KEY\""
            [[ -n "${GROQ_API_KEY:-}" ]] && echo "GROQ_API_KEY=\"$GROQ_API_KEY\""
            echo ""
        fi

        # API
        if svc_selected "api"; then
            echo "# ── Mascarade API ──"
            echo "API_PORT=\"${API_PORT:-3100}\""
            echo "CORE_URL=\"${CORE_URL:-http://core:${CORE_PORT:-8100}}\""
            echo "API_RUNTIME_UID=\"${API_RUNTIME_UID:-$(id -u)}\""
            echo "API_RUNTIME_GID=\"${API_RUNTIME_GID:-$(id -g)}\""
            echo "KILL_LIFE_ROOT=\"${KILL_LIFE_ROOT:-/workspace/Kill_LIFE}\""
            echo "OTEL_ENABLED=\"${OTEL_ENABLED:-false}\""
            echo "OTEL_COLLECTOR_HTTP_ENDPOINT=\"${OTEL_COLLECTOR_HTTP_ENDPOINT:-http://otel-collector:4318}\""
            echo "OPS_AGENT_URL=\"${OPS_AGENT_URL:-http://ops-agent:9200}\""
            echo "LOKI_URL=\"${LOKI_URL:-http://loki:3100}\""
            echo ""
        fi

        if svc_selected "agent-factory-cockpit"; then
            echo "# ── Industrial Cockpit ──"
            echo "AGENT_FACTORY_COCKPIT_PORT=\"${AGENT_FACTORY_COCKPIT_PORT:-4173}\""
            echo "AGENT_FACTORY_TRUSTED_PROXY_CIDRS=\"${AGENT_FACTORY_TRUSTED_PROXY_CIDRS:-172.16.0.0/12}\""
            echo "AGENT_FACTORY_OPERATOR_GROUPS=\"${AGENT_FACTORY_OPERATOR_GROUPS:-operator}\""
            echo "AGENT_FACTORY_APPROVER_GROUPS=\"${AGENT_FACTORY_APPROVER_GROUPS:-approver}\""
            echo "AGENT_FACTORY_AUDITOR_GROUPS=\"${AGENT_FACTORY_AUDITOR_GROUPS:-auditor}\""
            echo "AGENT_FACTORY_ADMIN_GROUPS=\"${AGENT_FACTORY_ADMIN_GROUPS:-admin}\""
            echo ""
        fi

        # Postgres
        if svc_selected "postgres"; then
            echo "# ── PostgreSQL ──"
            echo "POSTGRES_PORT=\"${POSTGRES_PORT:-5432}\""
            echo "POSTGRES_USER=\"${POSTGRES_USER:-mascarade}\""
            echo "POSTGRES_PASSWORD=\"$default_postgres_password\""
            echo "POSTGRES_DB=\"${POSTGRES_DB:-mascarade}\""
            echo ""
        fi

        # Redis
        if svc_selected "redis"; then
            echo "# ── Redis ──"
            echo "REDIS_PORT=\"${REDIS_PORT:-6379}\""
            echo ""
        fi

        # ClickHouse
        if svc_selected "clickhouse"; then
            echo "# ── ClickHouse ──"
            echo "CLICKHOUSE_HTTP_PORT=\"${CLICKHOUSE_HTTP_PORT:-8123}\""
            echo "CLICKHOUSE_NATIVE_PORT=\"${CLICKHOUSE_NATIVE_PORT:-9000}\""
            echo ""
        fi

        # Ollama
        if svc_selected "ollama" || [[ -n "${OLLAMA_BASE_URL:-}" ]] || [[ -n "${OLLAMA_HOST_MODE:-}" ]] || [[ "${OLLAMA_ENABLED:-false}" == "true" ]]; then
            local default_ollama_mode="${OLLAMA_HOST_MODE:-docker}"
            local default_ollama_url="http://ollama:${OLLAMA_PORT:-11434}"
            if [[ "$default_ollama_mode" == "native" ]]; then
                default_ollama_url="$(native_ollama_base_url "${OLLAMA_PORT:-11434}")"
            fi
            echo "# ── Ollama ──"
            echo "OLLAMA_PORT=\"${OLLAMA_PORT:-11434}\""
            echo "OLLAMA_ENABLED=\"true\""
            echo "OLLAMA_PUBLISH_PORT=\"${OLLAMA_PUBLISH_PORT:-true}\""
            echo "OLLAMA_USE_GPU=\"${OLLAMA_USE_GPU:-false}\""
            [[ -n "${OLLAMA_HOST_MODELS_DIR:-}" ]] && echo "OLLAMA_HOST_MODELS_DIR=\"${OLLAMA_HOST_MODELS_DIR}\""
            echo "OLLAMA_ENABLED=\"${OLLAMA_ENABLED:-$(svc_selected "ollama" && echo true || echo false)}\""
            echo "OLLAMA_HOST_MODE=\"${default_ollama_mode}\""
            echo "OLLAMA_BASE_URL=\"${OLLAMA_BASE_URL:-$default_ollama_url}\""
            echo ""
        fi

        if [[ -n "${APPLE_LLM_BASE_URL:-}" ]] || [[ "${APPLE_LLM_ENABLED:-false}" == "true" ]] || [[ -n "${APPLE_LLM_MODEL_PATH:-}" ]] || [[ -n "${APPLE_LLM_TOKENIZER_PATH:-}" ]]; then
            echo "# ── Apple LLM (service hote macOS) ──"
            echo "APPLE_LLM_ENABLED=\"${APPLE_LLM_ENABLED:-false}\""
            echo "APPLE_LLM_BASE_URL=\"${APPLE_LLM_BASE_URL:-http://host.docker.internal:${APPLE_LLM_PORT:-8201}}\""
            echo "APPLE_LLM_MODEL_ID=\"${APPLE_LLM_MODEL_ID:-apple-local}\""
            echo "APPLE_LLM_BACKEND=\"${APPLE_LLM_BACKEND:-coreml}\""
            echo "APPLE_LLM_HOST=\"${APPLE_LLM_HOST:-127.0.0.1}\""
            echo "APPLE_LLM_PORT=\"${APPLE_LLM_PORT:-8201}\""
            echo "APPLE_LLM_COMPUTE_UNITS=\"${APPLE_LLM_COMPUTE_UNITS:-cpu_and_ne}\""
            echo "APPLE_LLM_MODEL_PATH=\"${APPLE_LLM_MODEL_PATH:-}\""
            echo "APPLE_LLM_TOKENIZER_PATH=\"${APPLE_LLM_TOKENIZER_PATH:-}\""
            echo "APPLE_LLM_ENABLE_THINKING=\"${APPLE_LLM_ENABLE_THINKING:-false}\""
            echo "APPLE_LLM_MAX_INPUT_TOKENS=\"${APPLE_LLM_MAX_INPUT_TOKENS:-2048}\""
            echo "APPLE_LLM_MAX_NEW_TOKENS=\"${APPLE_LLM_MAX_NEW_TOKENS:-256}\""
            echo "APPLE_LLM_TRUST_REMOTE_CODE=\"${APPLE_LLM_TRUST_REMOTE_CODE:-false}\""
            echo "APPLE_LLM_TIMEOUT_SECONDS=\"${APPLE_LLM_TIMEOUT_SECONDS:-300}\""
            echo ""
        fi

        local default_litellm_master_key="${LITELLM_MASTER_KEY:-}"
        if [[ -z "$default_litellm_master_key" ]] && svc_selected "mem0"; then
            default_litellm_master_key="sk-mem0-local"
        fi

        # LiteLLM
        if svc_selected "litellm"; then
            echo "# ── LiteLLM ──"
            echo "LITELLM_PORT=\"${LITELLM_PORT:-4000}\""
            echo "LITELLM_MASTER_KEY=\"${default_litellm_master_key}\""
            echo ""
        fi

        # Langfuse
        if svc_selected "langfuse"; then
            echo "# ── Langfuse ──"
            echo "LANGFUSE_PORT=\"${LANGFUSE_PORT:-3200}\""
            echo "LANGFUSE_PUBLIC_ORIGIN=\"${LANGFUSE_PUBLIC_ORIGIN:-https://langfuse.saillant.cc}\""
            echo "LANGFUSE_INIT_PROJECT_PUBLIC_KEY=\"${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-}\""
            echo "LANGFUSE_INIT_PROJECT_SECRET_KEY=\"${LANGFUSE_INIT_PROJECT_SECRET_KEY:-}\""
            echo "CLICKHOUSE_USER=\"${CLICKHOUSE_USER:-langfuse}\""
            echo "CLICKHOUSE_PASSWORD=\"$default_clickhouse_password\""
            echo "CLICKHOUSE_MIGRATION_URL=\"${CLICKHOUSE_MIGRATION_URL:-clickhouse://clickhouse:9000}\""
            echo "MINIO_ROOT_USER=\"${MINIO_ROOT_USER:-minio}\""
            echo "MINIO_ROOT_PASSWORD=\"$default_minio_root_password\""
            echo "NEXTAUTH_URL=\"${NEXTAUTH_URL:-${LANGFUSE_PUBLIC_ORIGIN:-http://localhost:${LANGFUSE_PORT:-3200}}}\""
            echo "NEXTAUTH_SECRET=\"${NEXTAUTH_SECRET:-}\""
            echo "SALT=\"${SALT:-}\""
            echo "ENCRYPTION_KEY=\"${ENCRYPTION_KEY:-}\""
            echo ""
        fi

        if svc_selected "firecrawl"; then
            echo "# ── Firecrawl MCP ──"
            echo "FIRECRAWL_PORT=\"${FIRECRAWL_PORT:-3400}\""
            echo "FIRECRAWL_HOST=\"${FIRECRAWL_HOST:-0.0.0.0}\""
            echo "FIRECRAWL_API_KEY=\"${FIRECRAWL_API_KEY:-}\""
            echo "FIRECRAWL_API_URL=\"${FIRECRAWL_API_URL:-}\""
            echo ""
        fi

        if svc_selected "mem0"; then
            echo "# ── Mem0 / OpenMemory ──"
            echo "MEM0_PORT=\"${MEM0_PORT:-3300}\""
            echo "MEM0_USER=\"${MEM0_USER:-mascarade}\""
            echo "MEM0_OPENAI_API_KEY=\"${MEM0_OPENAI_API_KEY:-sk-mem0-local}\""
            echo "MEM0_OPENAI_BASE_URL=\"${MEM0_OPENAI_BASE_URL:-http://litellm:4000}\""
            echo "MEM0_QDRANT_HOST=\"${MEM0_QDRANT_HOST:-qdrant}\""
            echo "MEM0_QDRANT_PORT=\"${MEM0_QDRANT_PORT:-6333}\""
            echo ""
        fi

        # n8n
        if svc_selected "n8n"; then
            echo "# ── n8n ──"
            echo "N8N_PORT=\"${N8N_PORT:-5678}\""
            echo ""
        fi

        # Dify
        if svc_selected "dify"; then
            echo "# ── Dify ──"
            echo "DIFY_API_PORT=\"${DIFY_API_PORT:-5001}\""
            echo "DIFY_WEB_PORT=\"${DIFY_WEB_PORT:-3500}\""
            echo "DIFY_PUBLIC_ORIGIN=\"${DIFY_PUBLIC_ORIGIN:-https://dify.saillant.cc}\""
            echo "DIFY_PROXY_SERVER_NAME=\"${DIFY_PROXY_SERVER_NAME:-dify.saillant.cc}\""
            echo "DIFY_SECRET_KEY=\"${DIFY_SECRET_KEY:-}\""
            echo "OPENDAL_SCHEME=\"${OPENDAL_SCHEME:-fs}\""
            echo "OPENDAL_ROOT=\"${OPENDAL_ROOT:-/app/api/storage}\""
            echo ""
        fi

        # ComfyUI
        if svc_selected "comfyui" || [[ -n "${COMFYUI_URL:-}" || "${COMFYUI_LOCAL:-}" == "true" ]]; then
            echo "# ── ComfyUI ──"
            echo "COMFYUI_URL=\"${COMFYUI_URL:-}\""
            [[ "${COMFYUI_LOCAL:-}" == "true" ]] && echo "COMFYUI_LOCAL=\"true\""
            echo ""
        fi

        # TTS
        if svc_selected "tts"; then
            echo "# ── TTS ──"
            echo "TTS_PORT=\"${TTS_PORT:-10200}\""
            echo "TTS_ENGINE=\"${TTS_ENGINE:-piper}\""
            echo "TTS_VOICE=\"${TTS_VOICE:-}\""
            echo ""
        fi

        # STT
        if svc_selected "stt"; then
            echo "# ── STT ──"
            echo "STT_PORT=\"${STT_PORT:-9001}\""
            echo "STT_ENGINE=\"${STT_ENGINE:-faster_whisper}\""
            echo "STT_MODEL=\"${STT_MODEL:-small}\""
            echo ""
        fi

        # Generate Audio
        if svc_selected "generate-audio"; then
            echo "# ── Generate Audio ──"
            echo "GENERATE_AUDIO_PORT=\"${GENERATE_AUDIO_PORT:-9000}\""
            echo "GENERATE_AUDIO_ENGINE=\"${GENERATE_AUDIO_ENGINE:-audiogen}\""
            echo "GENERATE_AUDIO_MODEL=\"${GENERATE_AUDIO_MODEL:-facebook/audiogen-medium}\""
            echo "GENERATE_AUDIO_RUNTIME=\"${GENERATE_AUDIO_RUNTIME:-auto}\""
            echo "GENERATE_AUDIO_KEEP_LOADED=\"${GENERATE_AUDIO_KEEP_LOADED:-false}\""
            echo "GENERATE_AUDIO_IDLE_UNLOAD_SECONDS=\"${GENERATE_AUDIO_IDLE_UNLOAD_SECONDS:-0}\""
            echo "GENERATE_AUDIO_TORCH_VARIANT=\"${GENERATE_AUDIO_TORCH_VARIANT:-auto}\""
            echo "GENERATE_AUDIO_TORCH_VERSION=\"${GENERATE_AUDIO_TORCH_VERSION:-2.1.0}\""
            echo "GENERATE_AUDIO_TORCHAUDIO_VERSION=\"${GENERATE_AUDIO_TORCHAUDIO_VERSION:-2.1.0}\""
            echo "GENERATE_AUDIO_TORCHVISION_VERSION=\"${GENERATE_AUDIO_TORCHVISION_VERSION:-0.16.0}\""
            echo "GENERATE_AUDIO_TORCHTEXT_VERSION=\"${GENERATE_AUDIO_TORCHTEXT_VERSION:-0.16.0}\""
            echo "GENERATE_AUDIO_XFORMERS_VERSION=\"${GENERATE_AUDIO_XFORMERS_VERSION:-0.0.22.post7}\""
            echo "GENERATE_AUDIOCRAFT_VERSION=\"${GENERATE_AUDIOCRAFT_VERSION:-1.3.0}\""
            echo "GENERATE_AUDIO_TORCH_INDEX_URL=\"${GENERATE_AUDIO_TORCH_INDEX_URL:-}\""
            echo ""
        fi

        # Qdrant
        if svc_selected "qdrant"; then
            echo "# ── Qdrant ──"
            echo "QDRANT_PORT=\"${QDRANT_PORT:-6333}\""
            echo "QDRANT_GRPC_PORT=\"${QDRANT_GRPC_PORT:-6334}\""
            echo ""
        fi

        # Edge Proxy
        if svc_selected "edge-proxy"; then
            echo "# ── Edge Proxy ──"
            local default_proxy_password="${EDGE_PROXY_OPS_AUTH_PASSWORD:-$(_rand_secret 16)}"
            echo "EDGE_PROXY_BIND_HOST=\"${EDGE_PROXY_BIND_HOST:-0.0.0.0}\""
            echo "EDGE_PROXY_HTTP_PORT=\"${EDGE_PROXY_HTTP_PORT:-80}\""
            echo "EDGE_PROXY_HTTPS_PORT=\"${EDGE_PROXY_HTTPS_PORT:-443}\""
            echo "EDGE_PROXY_SERVER_NAME=\"${EDGE_PROXY_SERVER_NAME:-saillant.cc}\""
            echo "EDGE_PROXY_TLS_SANS=\"${EDGE_PROXY_TLS_SANS:-DNS:localhost,IP:127.0.0.1,DNS:saillant.cc,DNS:*.saillant.cc}\""
            echo "EDGE_PROXY_ACME_EMAIL=\"${EDGE_PROXY_ACME_EMAIL:-}\""
            echo "EDGE_PROXY_ACME_DOMAINS=\"${EDGE_PROXY_ACME_DOMAINS:-${EDGE_PROXY_SERVER_NAME:-saillant.cc},*.saillant.cc}\""
            echo "EDGE_PROXY_ACME_DNS_PROVIDER=\"${EDGE_PROXY_ACME_DNS_PROVIDER:-cloudflare}\""
            echo "EDGE_PROXY_ACME_CA=\"${EDGE_PROXY_ACME_CA:-letsencrypt}\""
            echo "EDGE_PROXY_ACME_KEY_LENGTH=\"${EDGE_PROXY_ACME_KEY_LENGTH:-ec-256}\""
            echo "EDGE_PROXY_ACME_DNS_SLEEP=\"${EDGE_PROXY_ACME_DNS_SLEEP:-30}\""
            echo "EDGE_PROXY_GRAFANA_SERVER_NAME=\"${EDGE_PROXY_GRAFANA_SERVER_NAME:-grafana.saillant.cc}\""
            echo "EDGE_PROXY_LANGFUSE_SERVER_NAME=\"${EDGE_PROXY_LANGFUSE_SERVER_NAME:-langfuse.saillant.cc}\""
            echo "EDGE_PROXY_OLLAMA_SERVER_NAME=\"${EDGE_PROXY_OLLAMA_SERVER_NAME:-ollama.saillant.cc}\""
            echo "EDGE_PROXY_PROMETHEUS_SERVER_NAME=\"${EDGE_PROXY_PROMETHEUS_SERVER_NAME:-prometheus.saillant.cc}\""
            echo "EDGE_PROXY_MEM0_SERVER_NAME=\"${EDGE_PROXY_MEM0_SERVER_NAME:-mem0.saillant.cc}\""
            echo "EDGE_PROXY_FIRECRAWL_SERVER_NAME=\"${EDGE_PROXY_FIRECRAWL_SERVER_NAME:-firecrawl.saillant.cc}\""
            echo "EDGE_PROXY_ZEROCLAW_SERVER_NAME=\"${EDGE_PROXY_ZEROCLAW_SERVER_NAME:-zeroclaw.saillant.cc}\""
            echo "EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME=\"${EDGE_PROXY_ZEROCLAW_DOCS_SERVER_NAME:-zeroclaw-docs.saillant.cc}\""
            echo "EDGE_PROXY_LANGGRAPH_SERVER_NAME=\"${EDGE_PROXY_LANGGRAPH_SERVER_NAME:-langgraph.saillant.cc}\""
            echo "EDGE_PROXY_INDUSTRIAL_SERVER_NAME=\"${EDGE_PROXY_INDUSTRIAL_SERVER_NAME:-industrial.saillant.cc}\""
            echo "EDGE_PROXY_OPS_AUTH_USER=\"${EDGE_PROXY_OPS_AUTH_USER:-ops}\""
            echo "EDGE_PROXY_OPS_AUTH_PASSWORD=\"${default_proxy_password}\""
            echo "ZEROCLAW_GATEWAY_URL=\"${ZEROCLAW_GATEWAY_URL:-http://host.docker.internal:3000}\""
            echo "ZEROCLAW_FOLLOW_URL=\"${ZEROCLAW_FOLLOW_URL:-http://host.docker.internal:8788}\""
            echo "CLOUDFLARE_API_TOKEN=\"${CLOUDFLARE_API_TOKEN:-}\""
            echo ""
        fi

        # Grafana
        if svc_selected "grafana"; then
            echo "# ── Grafana ──"
            echo "GRAFANA_PORT=\"${GRAFANA_PORT:-3001}\""
            echo "GRAFANA_PUBLIC_ORIGIN=\"${GRAFANA_PUBLIC_ORIGIN:-https://grafana.saillant.cc}\""
            echo ""
        fi

        if svc_selected "tempo"; then
            echo "# ── Tempo ──"
            echo "TEMPO_PORT=\"${TEMPO_PORT:-3201}\""
            echo ""
        fi

        # Prometheus
        if svc_selected "prometheus"; then
            echo "# ── Prometheus ──"
            echo "PROMETHEUS_PORT=\"${PROMETHEUS_PORT:-9090}\""
            echo ""
        fi

        if svc_selected "blackbox-exporter"; then
            echo "# ── Blackbox Exporter ──"
            echo "BLACKBOX_EXPORTER_PORT=\"${BLACKBOX_EXPORTER_PORT:-9115}\""
            echo ""
        fi

        if svc_selected "ops-agent"; then
            echo "# ── Ops Agent ──"
            echo "OPS_AGENT_PORT=\"${OPS_AGENT_PORT:-9200}\""
            echo "AGENTSIGHT_URL=\"${AGENTSIGHT_URL:-}\""
            echo ""
        fi

        if svc_selected "loki"; then
            echo "# ── Loki ──"
            echo "LOKI_PORT=\"${LOKI_PORT:-3101}\""
            echo ""
        fi

        if svc_selected "promtail"; then
            echo "# ── Promtail ──"
            echo "PROMTAIL_PORT=\"${PROMTAIL_PORT:-9080}\""
            echo ""
        fi

        if svc_selected "otel-collector"; then
            echo "# ── OpenTelemetry Collector ──"
            echo "OTEL_COLLECTOR_GRPC_PORT=\"${OTEL_COLLECTOR_GRPC_PORT:-4317}\""
            echo "OTEL_COLLECTOR_HTTP_PORT=\"${OTEL_COLLECTOR_HTTP_PORT:-4318}\""
            echo "OTEL_COLLECTOR_HEALTH_PORT=\"${OTEL_COLLECTOR_HEALTH_PORT:-13133}\""
            echo ""
        fi

        echo "# ── CAD / KiCad ──"
        echo "KICAD_VERSION=\"${KICAD_VERSION:-9.0}\""
        echo "KICAD_PLUGIN_DIR=\"${KICAD_PLUGIN_DIR:-}\""
        echo "CAD_WORKSPACE_DIR=\"${CAD_WORKSPACE_DIR:-}\""
        echo "CAD_INSTALL_BUNDLES=\"${CAD_INSTALL_BUNDLES:-all}\""
        echo ""

        # Integrations
        if [[ -n "${NOTION_API_KEY:-}" || -n "${KILL_LIFE_GITHUB_TOKEN:-}" || -n "${GITHUB_TOKEN:-}" ]]; then
            echo "# ── Integrations ──"
            [[ -n "${NOTION_API_KEY:-}" ]] && echo "NOTION_API_KEY=\"$NOTION_API_KEY\""
            [[ -n "${KILL_LIFE_GITHUB_TOKEN:-}" ]] && echo "KILL_LIFE_GITHUB_TOKEN=\"$KILL_LIFE_GITHUB_TOKEN\""
            [[ -n "${GITHUB_TOKEN:-}" ]] && echo "GITHUB_TOKEN=\"$GITHUB_TOKEN\""
            echo ""
        fi

    } > "$env_file"

    ok "Fichier .env ecrit : $env_file"
}
