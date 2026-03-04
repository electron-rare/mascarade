#!/usr/bin/env bash
# scripts/compose.sh — Generation du docker-compose.yml

generate_compose() {
    local output="${1:-$REPO_DIR/docker-compose.yml}"

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

        # Volumes
        echo ""
        echo "volumes:"
        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" != "1" ]] && continue
            local func="module_${id//-/_}_volumes"
            if declare -f "$func" &>/dev/null; then
                "$func"
            fi
        done

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

    # Backup si existant
    backup_file "$env_file"

    {
        echo "# .env — Genere par Mascarade setup — $(date '+%Y-%m-%d %H:%M')"
        echo ""

        # Core
        if svc_selected "core"; then
            echo "# ── Mascarade Core ──"
            echo "MASCARADE_API_KEY=\"${MASCARADE_API_KEY:-}\""
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

        # Postgres
        if svc_selected "postgres"; then
            echo "# ── PostgreSQL ──"
            echo "POSTGRES_PORT=\"${POSTGRES_PORT:-5432}\""
            echo "POSTGRES_USER=\"${POSTGRES_USER:-mascarade}\""
            echo "POSTGRES_PASSWORD=\"${POSTGRES_PASSWORD:-changeme}\""
            echo "POSTGRES_DB=\"${POSTGRES_DB:-mascarade}\""
            echo ""
        fi

        # Redis
        if svc_selected "redis"; then
            echo "# ── Redis ──"
            echo "REDIS_PORT=\"${REDIS_PORT:-6379}\""
            echo ""
        fi

        # Ollama
        if svc_selected "ollama"; then
            echo "# ── Ollama ──"
            echo "OLLAMA_PORT=\"${OLLAMA_PORT:-11434}\""
            echo ""
        fi

        # LiteLLM
        if svc_selected "litellm"; then
            echo "# ── LiteLLM ──"
            echo "LITELLM_PORT=\"${LITELLM_PORT:-4000}\""
            echo "LITELLM_MASTER_KEY=\"${LITELLM_MASTER_KEY:-}\""
            echo ""
        fi

        # Langfuse
        if svc_selected "langfuse"; then
            echo "# ── Langfuse ──"
            echo "LANGFUSE_PORT=\"${LANGFUSE_PORT:-3200}\""
            echo "LANGFUSE_SECRET_KEY=\"${LANGFUSE_SECRET_KEY:-}\""
            echo "LANGFUSE_NEXT_AUTH_SECRET=\"${LANGFUSE_NEXT_AUTH_SECRET:-}\""
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
            echo "DIFY_PORT=\"${DIFY_PORT:-3500}\""
            echo "DIFY_SECRET_KEY=\"${DIFY_SECRET_KEY:-}\""
            echo ""
        fi

        # ComfyUI
        if svc_selected "comfyui"; then
            echo "# ── ComfyUI ──"
            echo "COMFYUI_URL=\"${COMFYUI_URL:-}\""
            [[ "${COMFYUI_LOCAL:-}" == "true" ]] && echo "COMFYUI_LOCAL=\"true\""
            echo ""
        fi

        # TTS
        if svc_selected "tts"; then
            echo "# ── TTS ──"
            echo "TTS_PORT=\"${TTS_PORT:-10200}\""
            echo ""
        fi

        # STT
        if svc_selected "stt"; then
            echo "# ── STT ──"
            echo "STT_PORT=\"${STT_PORT:-9001}\""
            echo "STT_MODEL=\"${STT_MODEL:-small}\""
            echo ""
        fi

        # Generate Audio
        if svc_selected "generate-audio"; then
            echo "# ── Generate Audio ──"
            echo "GENERATE_AUDIO_PORT=\"${GENERATE_AUDIO_PORT:-9000}\""
            echo "GENERATE_AUDIO_MODEL=\"${GENERATE_AUDIO_MODEL:-small}\""
            echo ""
        fi

        # Qdrant
        if svc_selected "qdrant"; then
            echo "# ── Qdrant ──"
            echo "QDRANT_PORT=\"${QDRANT_PORT:-6333}\""
            echo ""
        fi

        # Grafana
        if svc_selected "grafana"; then
            echo "# ── Grafana ──"
            echo "GRAFANA_PORT=\"${GRAFANA_PORT:-3001}\""
            echo ""
        fi

        # Prometheus
        if svc_selected "prometheus"; then
            echo "# ── Prometheus ──"
            echo "PROMETHEUS_PORT=\"${PROMETHEUS_PORT:-9090}\""
            echo ""
        fi

        # Notion
        [[ -n "${NOTION_API_KEY:-}" ]] && echo "# ── Notion ──" && echo "NOTION_API_KEY=\"$NOTION_API_KEY\"" && echo ""

    } > "$env_file"

    ok "Fichier .env ecrit : $env_file"
}
