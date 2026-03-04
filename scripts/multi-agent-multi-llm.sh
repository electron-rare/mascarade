#!/usr/bin/env bash
# Bootstrap a multi-agent, multi-LLM team in Mascarade via API.

set -euo pipefail

API_URL="http://localhost:3100/api"
KEY="${KEY:-}"
MODE="pipeline"
PROMPT="Propose un plan d'action technique pour fiabiliser une stack IA locale."
PREFIX="team-ml"

usage() {
  cat <<'EOF'
Usage: multi-agent-multi-llm.sh [options]

Create 3 agents pinned to different LLM providers, then run orchestration.

Options:
  --api-url <url>       Base API URL (default: http://localhost:3100/api)
  --key <token>         API bearer token (or env KEY). Optional if auth disabled.
  --mode <mode>         orchestration mode: sequential|parallel|pipeline (default: pipeline)
  --prompt <text>       prompt sent to orchestrator
  --prefix <name>       prefix for created agents (default: team-ml)
  -h, --help            show help
EOF
}

err() { echo "error: $*" >&2; }
log() { echo "[$(date +%H:%M:%S)] $*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url)
      [[ $# -ge 2 ]] || { err "--api-url requires a value"; exit 2; }
      API_URL="$2"
      shift
      ;;
    --key)
      [[ $# -ge 2 ]] || { err "--key requires a value"; exit 2; }
      KEY="$2"
      shift
      ;;
    --mode)
      [[ $# -ge 2 ]] || { err "--mode requires a value"; exit 2; }
      MODE="$2"
      shift
      ;;
    --prompt)
      [[ $# -ge 2 ]] || { err "--prompt requires a value"; exit 2; }
      PROMPT="$2"
      shift
      ;;
    --prefix)
      [[ $# -ge 2 ]] || { err "--prefix requires a value"; exit 2; }
      PREFIX="$2"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "unknown option: $1"
      usage
      exit 2
      ;;
  esac
  shift
done

case "$MODE" in
  sequential|parallel|pipeline) ;;
  *)
    err "invalid mode: $MODE"
    exit 2
    ;;
esac

if [[ -z "$KEY" && -f ".env" ]]; then
  KEY="$(awk -F= '/^MASCARADE_API_KEY=/{gsub(/"/, "", $2); print $2}' .env | tail -n1)"
fi

if ! command -v curl >/dev/null 2>&1; then
  err "curl is required"
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  err "jq is required"
  exit 1
fi

json_hdr=("Content-Type: application/json")

curl_auth_args=()
if [[ -n "$KEY" ]]; then
  curl_auth_args=(-H "Authorization: Bearer $KEY")
fi

log "Fetching active providers..."
providers_json="$(curl -fsS "${curl_auth_args[@]}" "$API_URL/agents/providers")"
mapfile -t providers < <(echo "$providers_json" | jq -r '.providers[]')

if [[ ${#providers[@]} -eq 0 ]]; then
  err "no providers available. configure at least one API key in .env"
  exit 1
fi

pick_provider() {
  local preferred="$1"
  local candidate
  local p
  IFS=',' read -r -a candidate <<< "$preferred"
  for p in "${candidate[@]}"; do
    for ap in "${providers[@]}"; do
      if [[ "$ap" == "$p" ]]; then
        echo "$p"
        return 0
      fi
    done
  done
  echo "${providers[0]}"
}

planner_provider="$(pick_provider "claude,openai,google,mistral,huggingface,bedrock")"
coder_provider="$(pick_provider "openai,claude,mistral,huggingface,google,bedrock")"
review_provider="$(pick_provider "mistral,openai,claude,huggingface,google,bedrock")"

planner_agent="${PREFIX}-planner"
coder_agent="${PREFIX}-coder"
review_agent="${PREFIX}-reviewer"

upsert_agent() {
  local name="$1"
  local description="$2"
  local system_prompt="$3"
  local provider="$4"
  local temp="$5"
  local max_tokens="$6"
  local payload
  payload="$(jq -n \
    --arg name "$name" \
    --arg description "$description" \
    --arg system_prompt "$system_prompt" \
    --arg provider "$provider" \
    --argjson temperature "$temp" \
    --argjson max_tokens "$max_tokens" \
    '{
      name: $name,
      description: $description,
      system_prompt: $system_prompt,
      preferred_provider: $provider,
      strategy: "specific",
      temperature: $temperature,
      max_tokens: $max_tokens
    }')"

  curl -fsS -X POST "$API_URL/agents" \
    "${curl_auth_args[@]}" \
    -H "${json_hdr[0]}" \
    -d "$payload" >/dev/null
}

log "Creating agents with provider pinning..."
upsert_agent \
  "$planner_agent" \
  "Planifie l'approche et les étapes" \
  "Tu es un architecte technique. Fourni un plan court, concret, priorisé." \
  "$planner_provider" \
  "0.3" \
  "2048"

upsert_agent \
  "$coder_agent" \
  "Produit la solution technique" \
  "Tu es un lead engineer. Propose une implémentation claire avec étapes actionnables." \
  "$coder_provider" \
  "0.2" \
  "3072"

upsert_agent \
  "$review_agent" \
  "Challenge les risques et valide le plan" \
  "Tu es reviewer qualité/sécurité. Liste risques, régressions, tests manquants puis corrections." \
  "$review_provider" \
  "0.2" \
  "2048"

log "Running orchestration in '$MODE' mode..."
orchestrate_payload="$(jq -n \
  --arg prompt "$PROMPT" \
  --arg mode "$MODE" \
  --arg a1 "$planner_agent" \
  --arg a2 "$coder_agent" \
  --arg a3 "$review_agent" \
  '{agent_names: [$a1, $a2, $a3], prompt: $prompt, mode: $mode}')"

result="$(curl -fsS -X POST "$API_URL/agents/orchestrate" \
  "${curl_auth_args[@]}" \
  -H "${json_hdr[0]}" \
  -d "$orchestrate_payload")"

echo ""
echo "Agents provisioned:"
echo "  - $planner_agent ($planner_provider)"
echo "  - $coder_agent ($coder_provider)"
echo "  - $review_agent ($review_provider)"
echo ""
echo "Orchestration result:"
echo "$result" | jq .
