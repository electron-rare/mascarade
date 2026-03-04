#!/usr/bin/env bash
# scripts/compose.sh — Generation du docker-compose.yml

generate_compose() {
    local output="${1:-$REPO_DIR/docker-compose.yml}"
    dbg "generate_compose: output=$output"

    # Charger tous les modules
    local mod_count=0
    for mod_file in "$REPO_DIR/scripts/modules/"*.sh; do
        dbg "  source $(basename "$mod_file")"
        # shellcheck disable=SC1090
        source "$mod_file"
        ((mod_count++)) || true
    done
    dbg "  $mod_count modules charges"

    {
        # Header
        cat <<'HEADER'
# docker-compose.yml — Genere par Mascarade setup
# Ne pas editer manuellement, utiliser ./config pour reconfigurer

services:
HEADER

        # Services selectionnes
        local svc_count=0
        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" != "1" ]] && continue
            local func="module_${id//-/_}_compose"
            if declare -f "$func" &>/dev/null; then
                dbg "  compose: $func (service $id)"
                "$func"
                echo ""
                ((svc_count++)) || true
            else
                dbg "  compose: $func NON DEFINI pour $id"
            fi
        done
        dbg "  $svc_count services generes"

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
                dbg "  volumes: $func (service $id)"
                "$func"
            fi
        done

    } > "$output"
    dbg "generate_compose: termine ($(wc -l < "$output") lignes)"
}

# ── Collecte de la configuration .env de tous les modules ──
collect_module_configs() {
    dbg "collect_module_configs: debut"
    local mod_count=0
    for mod_file in "$REPO_DIR/scripts/modules/"*.sh; do
        dbg "  source $(basename "$mod_file")"
        # shellcheck disable=SC1090
        source "$mod_file"
        ((mod_count++)) || true
    done
    dbg "  $mod_count modules charges"

    local config_count=0
    for id in "${SVC_IDS[@]}"; do
        [[ "${SVC_ON[$id]}" != "1" ]] && continue
        local func="module_${id//-/_}_config"
        if declare -f "$func" &>/dev/null; then
            local label="${SVC_LABEL[$id]}"
            dbg "  config: $func ($label)"
            echo ""
            log "Configuration ${label}..."
            "$func"
            ((config_count++)) || true
        else
            dbg "  config: $func NON DEFINI pour $id"
        fi
    done
    dbg "collect_module_configs: $config_count modules configures"
}

# ── Ecriture du fichier .env ──
write_env_file() {
    local env_file="${1:-$REPO_DIR/.env}"
    dbg "write_env_file: $env_file"

    # Backup si existant
    backup_file "$env_file"

    local var_count=0

    {
        echo "# .env — Genere par Mascarade setup — $(date '+%Y-%m-%d %H:%M')"
        echo ""

        # Core
        if svc_selected "core"; then
            dbg "  section: Core"
            echo "# ── Mascarade Core ──"
            echo "CORE_PORT=\"${CORE_PORT:-8100}\""
            echo "CORE_HOST=\"${CORE_HOST:-0.0.0.0}\""
            echo "DEFAULT_PROVIDER=\"${DEFAULT_PROVIDER:-anthropic}\""
            echo "DEFAULT_MODEL=\"${DEFAULT_MODEL:-claude-sonnet-4-6}\""
            echo "MASCARADE_API_KEY=\"${MASCARADE_API_KEY:-}\""
            echo "DEFAULT_LLM_PROVIDER=\"${DEFAULT_LLM_PROVIDER:-anthropic}\""
            echo "DEFAULT_LLM_MODEL=\"${DEFAULT_LLM_MODEL:-claude-sonnet-4-20250514}\""
            echo ""
            echo "# ── Cles API LLM ──"
            [[ -n "${ANTHROPIC_API_KEY:-}" ]] && echo "ANTHROPIC_API_KEY=\"$ANTHROPIC_API_KEY\"" && dbg "  ANTHROPIC_API_KEY=presente"
            [[ -n "${OPENAI_API_KEY:-}" ]] && echo "OPENAI_API_KEY=\"$OPENAI_API_KEY\"" && dbg "  OPENAI_API_KEY=presente"
            [[ -n "${GOOGLE_API_KEY:-}" ]] && echo "GOOGLE_API_KEY=\"$GOOGLE_API_KEY\"" && dbg "  GOOGLE_API_KEY=presente"
            [[ -n "${MISTRAL_API_KEY:-}" ]] && echo "MISTRAL_API_KEY=\"$MISTRAL_API_KEY\"" && dbg "  MISTRAL_API_KEY=presente"
            [[ -n "${GROQ_API_KEY:-}" ]] && echo "GROQ_API_KEY=\"$GROQ_API_KEY\"" && dbg "  GROQ_API_KEY=presente"
            echo ""
            ((var_count += 7)) || true
        fi

        # API
        if svc_selected "api"; then
            dbg "  section: API (API_PORT=${API_PORT:-3100} CORE_URL=${CORE_URL:-auto})"
            echo "# ── Mascarade API ──"
            echo "API_PORT=\"${API_PORT:-3100}\""
            echo "CORE_URL=\"${CORE_URL:-http://core:${CORE_PORT:-8100}}\""
            echo ""
            ((var_count += 2)) || true
        fi

        # Postgres
        if svc_selected "postgres"; then
            dbg "  section: PostgreSQL (port=${POSTGRES_PORT:-5432})"
            echo "# ── PostgreSQL ──"
            echo "POSTGRES_PORT=\"${POSTGRES_PORT:-5432}\""
            echo "POSTGRES_USER=\"${POSTGRES_USER:-mascarade}\""
            echo "POSTGRES_PASSWORD=\"${POSTGRES_PASSWORD:-changeme}\""
            echo "POSTGRES_DB=\"${POSTGRES_DB:-mascarade}\""
            echo ""
            ((var_count += 4)) || true
        fi

        # Redis
        if svc_selected "redis"; then
            dbg "  section: Redis (port=${REDIS_PORT:-6379})"
            echo "# ── Redis ──"
            echo "REDIS_PORT=\"${REDIS_PORT:-6379}\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Ollama
        if svc_selected "ollama"; then
            dbg "  section: Ollama (port=${OLLAMA_PORT:-11434})"
            echo "# ── Ollama ──"
            echo "OLLAMA_PORT=\"${OLLAMA_PORT:-11434}\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Open WebUI
        if svc_selected "open-webui"; then
            dbg "  section: Open WebUI (port=${OPEN_WEBUI_PORT:-8080})"
            echo "# ── Open WebUI ──"
            echo "OPEN_WEBUI_PORT=\"${OPEN_WEBUI_PORT:-8080}\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Ops Console
        if svc_selected "ops-console"; then
            dbg "  section: Ops Console (port=${OPS_CONSOLE_PORT:-80})"
            echo "# ── Ops Console ──"
            echo "OPS_CONSOLE_BIND_IP=\"${OPS_CONSOLE_BIND_IP:-127.0.0.1}\""
            echo "OPS_CONSOLE_PORT=\"${OPS_CONSOLE_PORT:-80}\""
            echo ""
            ((var_count += 2)) || true
        fi

        # LiteLLM
        if svc_selected "litellm"; then
            dbg "  section: LiteLLM (port=${LITELLM_PORT:-4000})"
            echo "# ── LiteLLM ──"
            echo "LITELLM_PORT=\"${LITELLM_PORT:-4000}\""
            echo "LITELLM_MASTER_KEY=\"${LITELLM_MASTER_KEY:-}\""
            echo ""
            ((var_count += 2)) || true
        fi

        # Langfuse
        if svc_selected "langfuse"; then
            dbg "  section: Langfuse (port=${LANGFUSE_PORT:-3200})"
            echo "# ── Langfuse ──"
            echo "LANGFUSE_PORT=\"${LANGFUSE_PORT:-3200}\""
            echo "LANGFUSE_SECRET_KEY=\"${LANGFUSE_SECRET_KEY:-}\""
            echo "LANGFUSE_NEXT_PUBLIC_KEY=\"${LANGFUSE_NEXT_PUBLIC_KEY:-}\""
            echo "NEXTAUTH_URL=\"${NEXTAUTH_URL:-http://localhost:${LANGFUSE_PORT:-3200}}\""
            echo "NEXTAUTH_SECRET=\"${NEXTAUTH_SECRET:-}\""
            echo "SALT=\"${SALT:-}\""
            echo "ENCRYPTION_KEY=\"${ENCRYPTION_KEY:-}\""
            echo ""
            ((var_count += 7)) || true
        fi

        # n8n
        if svc_selected "n8n"; then
            dbg "  section: n8n (port=${N8N_PORT:-5678})"
            echo "# ── n8n ──"
            echo "N8N_PORT=\"${N8N_PORT:-5678}\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Dify
        if svc_selected "dify"; then
            dbg "  section: Dify (api_port=${DIFY_API_PORT:-5001} web_port=${DIFY_WEB_PORT:-3500})"
            echo "# ── Dify ──"
            echo "DIFY_API_PORT=\"${DIFY_API_PORT:-5001}\""
            echo "DIFY_WEB_PORT=\"${DIFY_WEB_PORT:-3500}\""
            echo "DIFY_SECRET_KEY=\"${DIFY_SECRET_KEY:-}\""
            echo ""
            ((var_count += 3)) || true
        fi

        # ComfyUI
        if svc_selected "comfyui"; then
            dbg "  section: ComfyUI (url=${COMFYUI_URL:-vide} local=${COMFYUI_LOCAL:-false})"
            echo "# ── ComfyUI ──"
            echo "COMFYUI_URL=\"${COMFYUI_URL:-}\""
            [[ "${COMFYUI_LOCAL:-}" == "true" ]] && echo "COMFYUI_LOCAL=\"true\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Qdrant
        if svc_selected "qdrant"; then
            dbg "  section: Qdrant (port=${QDRANT_PORT:-6333})"
            echo "# ── Qdrant ──"
            echo "QDRANT_PORT=\"${QDRANT_PORT:-6333}\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Grafana
        if svc_selected "grafana"; then
            dbg "  section: Grafana (port=${GRAFANA_PORT:-3001})"
            echo "# ── Grafana ──"
            echo "GRAFANA_PORT=\"${GRAFANA_PORT:-3001}\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Prometheus
        if svc_selected "prometheus"; then
            dbg "  section: Prometheus (port=${PROMETHEUS_PORT:-9090})"
            echo "# ── Prometheus ──"
            echo "PROMETHEUS_PORT=\"${PROMETHEUS_PORT:-9090}\""
            echo ""
            ((var_count += 1)) || true
        fi

        # Notion
        if [[ -n "${NOTION_API_KEY:-}" ]]; then
            dbg "  section: Notion (key presente)"
            echo "# ── Notion ──"
            echo "NOTION_API_KEY=\"$NOTION_API_KEY\""
            echo ""
            ((var_count += 1)) || true
        fi

    } > "$env_file"

    dbg "write_env_file: $var_count variables ecrites dans $env_file ($(wc -l < "$env_file") lignes)"
    ok "Fichier .env ecrit : $env_file"
}
