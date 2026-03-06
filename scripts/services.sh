#!/usr/bin/env bash
# scripts/services.sh — Definitions des services Mascarade

# ── Tableaux ──
declare -a SVC_IDS=()
declare -A SVC_LABEL=() SVC_DESC=() SVC_PORT=() SVC_CAT=() SVC_ON=() SVC_DEPS=()

define_service() {
    local id="$1" label="$2" desc="$3" port="$4" cat="$5" on="${6:-0}" deps="${7:-}"
    SVC_IDS+=("$id")
    SVC_LABEL[$id]="$label"
    SVC_DESC[$id]="$desc"
    SVC_PORT[$id]="$port"
    SVC_CAT[$id]="$cat"
    SVC_ON[$id]="$on"
    SVC_DEPS[$id]="$deps"
}

# ── Mascarade ──
define_service "core"       "Mascarade Core"    "FastAPI — routeur LLM, agents, orchestrateur"    "8100"  "mascarade" 1 ""
define_service "api"        "Mascarade API"     "Hono — gateway HTTP, auth middleware"             "3100"  "mascarade" 1 "core"

# ── Outils ──
define_service "litellm"    "LiteLLM"           "Proxy LLM unifie + cache Redis"                  "4000"  "tools" 0 "redis"
define_service "n8n"        "n8n"               "Automatisation workflows low-code"                "5678"  "tools" 0 "postgres"
define_service "langfuse"   "Langfuse"          "Observabilite LLM (tracing, evals)"              "3200"  "tools" 0 "postgres,clickhouse"
define_service "dify"       "Dify"              "App builder IA (API + Web + Worker)"              "3500"  "tools" 0 "postgres,redis"
define_service "clickhouse" "ClickHouse"        "Base analytique colonnaire (Langfuse)"            "—"     "tools" 0 ""
define_service "comfyui"    "ComfyUI"           "Generation d'images (SD, Flux)"                   "8188"  "tools" 0 ""
define_service "tts"        "TTS"               "Synthese vocale locale (Piper/Wyoming)"           "10200" "tools" 0 ""
define_service "stt"        "STT"               "Speech-to-text local (Whisper multi-engine)"      "9001"  "tools" 0 ""
define_service "generate-audio" "Generate Audio" "Generation audio locale (AudioCraft AudioGen/MusicGen, CPU/GPU)" "9000"  "tools" 0 ""

# ── Infrastructure ──
define_service "ollama"     "Ollama"            "Serveur LLM local (llama, mistral, etc.)"        "11434" "infra" 0 ""
define_service "open-webui" "Open WebUI"        "Interface chat pour Ollama"                       "8080"  "infra" 0 "ollama"
define_service "ops-console" "Ops Console"      "Cockpit web (accueil et liens de la stack)"       "80"    "infra" 0 ""
define_service "edge-proxy" "Edge Proxy"        "Reverse proxy HTTP/HTTPS pour l'API et ops-console" "80/443" "infra" 0 "api,ops-console"
define_service "redis"      "Redis"             "Cache & broker (LiteLLM, Dify)"                   "6379"  "infra" 0 ""
define_service "postgres"   "PostgreSQL"        "Base relationnelle (Langfuse, Dify, n8n)"         "5432"  "infra" 0 ""
define_service "qdrant"     "Qdrant"            "Base vectorielle (embeddings, RAG)"               "6333"  "infra" 0 ""
define_service "grafana"    "Grafana"           "Dashboards monitoring"                            "3001"  "infra" 0 ""
define_service "prometheus" "Prometheus"        "Collecte metriques"                               "9090"  "infra" 0 ""
define_service "loki"       "Loki"              "Historique des logs et traces structurees"        "3101"  "infra" 0 ""
define_service "promtail"   "Promtail"          "Collecte Docker/journald vers Loki"               "9080"  "infra" 0 "loki"
define_service "otel-collector" "OTel Collector" "Recepteur OTLP et point d'export observability"  "4318"  "infra" 0 ""

dbg "services.sh: ${#SVC_IDS[@]} services definis"

# ── Helpers ──
svc_selected() { [[ "${SVC_ON[${1}]:-0}" == "1" ]]; }

svc_dep_satisfied_by_host() {
    local id="$1" dep="$2"
    if [[ "$id" == "open-webui" && "$dep" == "ollama" && "${OLLAMA_HOST_MODE:-docker}" == "native" ]]; then
        return 0
    fi
    return 1
}

sync_service_ports_from_env() {
    local id env_var value
    for id in "${SVC_IDS[@]}"; do
        case "$id" in
            core) env_var="CORE_PORT" ;;
            api) env_var="API_PORT" ;;
            litellm) env_var="LITELLM_PORT" ;;
            n8n) env_var="N8N_PORT" ;;
            langfuse) env_var="LANGFUSE_PORT" ;;
            dify) env_var="DIFY_WEB_PORT" ;;
            comfyui) env_var="COMFYUI_PORT" ;;
            tts) env_var="TTS_PORT" ;;
            stt) env_var="STT_PORT" ;;
            generate-audio) env_var="GENERATE_AUDIO_PORT" ;;
            ollama) env_var="OLLAMA_PORT" ;;
            open-webui) env_var="OPEN_WEBUI_PORT" ;;
            ops-console) env_var="OPS_CONSOLE_PORT" ;;
            edge-proxy) env_var="EDGE_PROXY_HTTP_PORT" ;;
            redis) env_var="REDIS_PORT" ;;
            postgres) env_var="POSTGRES_PORT" ;;
            qdrant) env_var="QDRANT_PORT" ;;
            grafana) env_var="GRAFANA_PORT" ;;
            prometheus) env_var="PROMETHEUS_PORT" ;;
            loki) env_var="LOKI_PORT" ;;
            promtail) env_var="PROMTAIL_PORT" ;;
            otel-collector) env_var="OTEL_COLLECTOR_HTTP_PORT" ;;
            *)
                env_var=""
                ;;
        esac

        [[ -z "$env_var" ]] && continue
        value="${!env_var:-}"
        [[ -n "$value" ]] && SVC_PORT[$id]="$value"
    done

    return 0
}

selected_in_cat() {
    local cat="$1"
    for id in "${SVC_IDS[@]}"; do
        [[ "${SVC_CAT[$id]}" == "$cat" && "${SVC_ON[$id]}" == "1" ]] && echo "$id"
    done
}

# ── Resolution des dependances ──
resolve_dependencies() {
    dbg "resolve_dependencies: debut"
    local changed=true
    local pass=0
    local max_passes=${#SVC_IDS[@]}
    while $changed; do
        changed=false
        ((pass++)) || true
        if (( pass > max_passes )); then
            err "Cycle detecte dans les dependances de services (apres $pass passes)"
            exit 2
        fi
        dbg "  passe $pass..."
        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" != "1" ]] && continue
            local deps="${SVC_DEPS[$id]}"
            [[ -z "$deps" ]] && continue
            IFS=',' read -ra dep_list <<< "$deps"
            for dep in "${dep_list[@]}"; do
                if svc_dep_satisfied_by_host "$id" "$dep"; then
                    info "${SVC_LABEL[$id]} utilisera ${SVC_LABEL[$dep]} sur l'hote — pas de conteneur ${SVC_LABEL[$dep]} ajoute"
                    continue
                fi
                if [[ "${SVC_ON[$dep]:-0}" != "1" ]]; then
                    SVC_ON[$dep]="1"
                    changed=true
                    dbg "    $id requiert $dep → active"
                    info "${SVC_LABEL[$id]} requiert ${SVC_LABEL[$dep]} — active automatiquement"
                fi
            done
        done
    done
    dbg "resolve_dependencies: termine ($pass passes)"

    # Resume
    dbg "Etat final des services:"
    for id in "${SVC_IDS[@]}"; do
        dbg "  $id: ${SVC_ON[$id]} (${SVC_LABEL[$id]}, deps=${SVC_DEPS[$id]:-aucune})"
    done
}

# ── Charger l'etat actuel depuis docker compose ──
load_running_services() {
    local compose_file="${REPO_DIR}/docker-compose.yml"
    dbg "load_running_services: $compose_file"
    if [[ ! -f "$compose_file" ]]; then
        dbg "  fichier absent"
        return 1
    fi
    local services
    services=$(docker_compose_cmd -f "$compose_file" config --services 2>/dev/null || true)
    if [[ -z "$services" ]]; then
        dbg "  aucun service retourne par docker compose config"
        return 1
    fi
    dbg "  services dans compose: $(echo "$services" | tr '\n' ' ')"
    # Mark all as off, then enable those found
    for id in "${SVC_IDS[@]}"; do SVC_ON[$id]="0"; done
    while IFS= read -r svc; do
        for id in "${SVC_IDS[@]}"; do
            if [[ "$svc" == "$id" || "$svc" == "${id}-"* ]]; then
                SVC_ON[$id]="1"
                dbg "  $id → ON (match '$svc')"
            fi
        done
    done <<< "$services"
    return 0
}
