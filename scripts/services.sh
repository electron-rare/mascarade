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
define_service "generate-audio" "Generate Audio" "API audio (transcription/traitement)"            "9000"  "tools" 0 ""

# ── Infrastructure ──
define_service "ollama"     "Ollama"            "Serveur LLM local (llama, mistral, etc.)"        "11434" "infra" 0 ""
define_service "open-webui" "Open WebUI"        "Interface chat pour Ollama"                       "8080"  "infra" 0 "ollama"
define_service "ops-console" "Ops Console"      "Cockpit web (accueil et liens de la stack)"       "80"    "infra" 0 ""
define_service "redis"      "Redis"             "Cache & broker (LiteLLM, Dify)"                   "6379"  "infra" 0 ""
define_service "postgres"   "PostgreSQL"        "Base relationnelle (Langfuse, Dify, n8n)"         "5432"  "infra" 0 ""
define_service "qdrant"     "Qdrant"            "Base vectorielle (embeddings, RAG)"               "6333"  "infra" 0 ""
define_service "grafana"    "Grafana"           "Dashboards monitoring"                            "3001"  "infra" 0 ""
define_service "prometheus" "Prometheus"        "Collecte metriques"                               "9090"  "infra" 0 ""

dbg "services.sh: ${#SVC_IDS[@]} services definis"

# ── Helpers ──
svc_selected() { [[ "${SVC_ON[${1}]:-0}" == "1" ]]; }

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
    while $changed; do
        changed=false
        ((pass++)) || true
        dbg "  passe $pass..."
        for id in "${SVC_IDS[@]}"; do
            [[ "${SVC_ON[$id]}" != "1" ]] && continue
            local deps="${SVC_DEPS[$id]}"
            [[ -z "$deps" ]] && continue
            IFS=',' read -ra dep_list <<< "$deps"
            for dep in "${dep_list[@]}"; do
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
