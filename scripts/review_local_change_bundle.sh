#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="status"
BUNDLE=""

usage() {
  cat <<'EOF'
Usage: bash scripts/review_local_change_bundle.sh <bundle> [mode]

Bundles:
  mcp-runtime-surfaces    API/core/web autour de knowledge-base, CAD et suppression notion
  ops-observability-runtime  Langfuse, ops, dashboards, compose, probes et runtime tools
  finetune-followups      Correctifs finetune + fix API JSON associe
  docs-state              Plans, TODO, README et cartographie locale
  all                     Ensemble des lots suivis localement

Modes:
  status   git status cible sur le bundle (default)
  diff     git diff cible sur le bundle
  paths    liste exacte des fichiers du bundle
EOF
}

bundle_paths() {
  case "$1" in
    mcp-runtime-surfaces)
      cat <<'EOF'
api/src/client/core.ts
api/src/index.ts
api/src/lib/killlife.ts
api/src/routes/agents.ts
api/src/routes/settings.ts
api/src/routes/cad.test.ts
api/src/routes/cad.ts
api/src/routes/knowledgeBase.ts
api/src/routes/notion.ts
core/mascarade/agents/freecad_agent.py
core/mascarade/agents/skills.py
core/mascarade/integrations/__init__.py
core/mascarade/integrations/github_dispatch.py
core/mascarade/integrations/knowledge_base.py
core/mascarade/integrations/notion.py
core/mascarade/mcp/
core/mascarade/server.py
core/tests/test_knowledge_base.py
core/tests/test_mcp_client.py
core/tests/test_notion.py
core/tests/test_server_cad_mcp.py
core/tests/test_server_knowledge_base_mcp.py
core/tests/test_skills.py
docs/MCP_AGENTICS_ARCHITECTURE.md
docs/FRONTEND_SPEC.md
web/src/App.tsx
web/src/api/cad.ts
web/src/api/knowledgeBase.ts
web/src/api/notion.ts
web/src/components/layout/navigation.ts
web/src/pages/KnowledgeBrowser.tsx
web/src/pages/NotionBrowser.tsx
web/src/pages/Orchestrate.tsx
web/src/pages/Settings.tsx
EOF
      ;;
    ops-observability-runtime)
      cat <<'EOF'
.env.example
api/src/routes/ops.test.ts
api/src/routes/ops.ts
core/mascarade/config.py
core/mascarade/observability/agent_trace.py
core/mascarade/observability/langfuse.py
core/mascarade/router/router.py
core/pyproject.toml
core/tests/test_mistral_provider.py
core/tests/test_orchestrator.py
core/tests/test_provider_admin.py
core/tests/test_router.py
deploy/Dockerfile.core
deploy/grafana/provisioning/dashboards/json/mascarade-ai-runtime.json
deploy/migration/python-tools.extras.requirements.txt
deploy/ops_agent/app.py
deploy/prometheus/blackbox.yml
docker-compose.yml
scripts/bootstrap_python_tools_env.sh
scripts/compose.sh
scripts/modules/core.sh
scripts/modules/memos.sh
scripts/modules/ops-agent.sh
scripts/services.sh
scripts/smoke_mem0.sh
web/src/api/ops.ts
web/src/pages/Logs.tsx
web/src/pages/OpsHub.tsx
EOF
      ;;
    finetune-followups)
      cat <<'EOF'
api/src/middleware/error.test.ts
api/src/middleware/error.ts
finetune/pipeline.py
finetune/promote_model.py
EOF
      ;;
    docs-state)
      cat <<'EOF'
CLAUDE.md
MANIFEST.md
README.md
TODO_COCKPIT_OPS.md
TODO_IMPLEMENTE.md
TODO_TUNNING_PARTY.md
TODO_VM.md
config
docs/EXECUTION_PLAN_2026-03-07.md
docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md
docs/MCP_AGENTICS_ARCHITECTURE.md
docs/RUNBOOK_VM_OPS.md
docs/audit/REMEDIATION_BACKLOG_2026-03-07_REAUDIT.md
docs/audit/REMEDIATION_STATUS_2026-03-08.md
scripts/review_local_change_bundle.sh
EOF
      ;;
    all)
      {
        bundle_paths mcp-runtime-surfaces
        bundle_paths ops-observability-runtime
        bundle_paths finetune-followups
        bundle_paths docs-state
      } | awk '!seen[$0]++'
      ;;
    *)
      echo "Unknown bundle: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage >&2
  exit 2
fi

BUNDLE="$1"
if [[ $# -eq 2 ]]; then
  MODE="$2"
fi

mapfile -t PATHS < <(bundle_paths "$BUNDLE")

case "$MODE" in
  status)
    exec git -C "$ROOT_DIR" status --short -- "${PATHS[@]}"
    ;;
  diff)
    exec git -C "$ROOT_DIR" diff -- "${PATHS[@]}"
    ;;
  paths)
    printf '%s\n' "${PATHS[@]}"
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    usage >&2
    exit 2
    ;;
esac
