# Local Change Bundles — 2026-03-08

But: figer le residuel local de `mascarade` en lots de commit explicites,
avec le statut reel apres rejeu des checks canoniques du `2026-03-08`.

## Etat courant

Commits locaux deja sortis:

1. `e9de1e0` — `mcp-runtime-surfaces`
2. `1e50bea` — `ops-observability-runtime`
3. `8291d3e` — `docs-state`

Etat residuel:

- un reliquat suivi reste ouvert dans `mascarade`
- `Kill_LIFE` est pret cote repo suivi hors mise a jour documentaire locale; seul `.mascarade/` reste local/exclu
- `crazy_life` passe son preflight de publication local; seul ce document d'etat reste modifie dans son worktree
- le prochain travail n'est plus de rouvrir la pile `MCP/agentics`; c'est de
  publier proprement les bundles locaux restants

Checks canoniques rejoues avec succes sur `mascarade`:

- `bash scripts/test_python.sh --bootstrap --venv-dir /tmp/mascarade-plan-impl-2`
- `cd api && npm run build`
- `cd web && npm run build`
- `docker compose config -q`
- `GET /api/ops/summary` authentifie -> `mcp.aggregate_status=ready`, `7/7`
  serveurs `ready`

Reliquats suivis actuels:

1. `runtime-core-fixes`
2. `ops-observability-followups`
3. `docs-state`
4. `finetune/kicad_kic_ai` reste dirty dans le repo imbrique et n'entre pas
   dans le bundle `mascarade` courant

## Bundle `runtime-core-fixes`

Objet:

- recoller le chemin Python canonique a l'etat reel du runtime courant
- couvrir les champs `knowledge-base`/MCP et le proxy `Mistral` attendus par
  les tests repo-locaux

Fichiers:

- `api/src/routes/agents.ts`
- `core/mascarade/agents/skills.py`
- `core/mascarade/config.py`
- `core/mascarade/observability/agent_trace.py`
- `core/mascarade/router/providers/mistral.py`
- `web/src/api/agents.ts`
- `web/src/pages/AgentDetail.tsx`

Validation minimale:

```bash
cd /home/clems/mascarade/core && \
  /home/clems/mascarade/core/.venv/bin/python -m pytest \
    tests/test_knowledge_base.py \
    tests/test_mistral_provider.py \
    tests/test_mcp_client.py -q
bash /home/clems/mascarade/scripts/test_python.sh --bootstrap \
  --venv-dir /tmp/mascarade-plan-impl-2
```

Commit recommande:

```bash
git add api/src/routes/agents.ts \
  core/mascarade/agents/skills.py \
  core/mascarade/config.py \
  core/mascarade/observability/agent_trace.py \
  core/mascarade/router/providers/mistral.py
git commit -m "core(runtime): realign canonical python paths"
```

## Bundle `ops-observability-followups`

Objet:

- figer le reliquat observabilite encore local dans `mascarade`
- publier ensemble les morceaux `tempo` / `blackbox` / service wiring restants

Fichiers:

- `.env.example`
- `api/public/`
- `api/src/routes/ops.ts`
- `deploy/Dockerfile.edge-proxy`
- `deploy/edge-proxy/20-generate-ops-auth.sh`
- `deploy/edge-proxy/default.conf.template`
- `deploy/grafana/provisioning/dashboards/json/mascarade-tooling-observability.json`
- `deploy/grafana/provisioning/datasources/datasources.yaml`
- `deploy/otel-collector/config.yaml`
- `deploy/prometheus/blackbox.yml`
- `deploy/prometheus/prometheus.yml`
- `deploy/tempo/`
- `docker-compose.yml`
- `scripts/compose.sh`
- `scripts/modules/edge-proxy.sh`
- `scripts/modules/grafana.sh`
- `scripts/modules/langfuse.sh`
- `scripts/modules/otel-collector.sh`
- `scripts/modules/prometheus.sh`
- `scripts/modules/blackbox-exporter.sh`
- `scripts/modules/tempo.sh`
- `scripts/services.sh`
- `web/src/api/ops.ts`
- `web/src/pages/Logs.tsx`
- `web/src/pages/OpsHub.tsx`
- `web/src/pages/Orchestrate.tsx`

## Bundle `docs-state`

Objet:

- realigner les TODO/plans/documents d'etat sur le runtime reel
- figer la cartographie des bundles et le statut de remediations fermees
- documenter le passage en phase de publication multi-repo

Fichiers:

- `TODO_COCKPIT_OPS.md`
- `docs/MCP_AGENTICS_ARCHITECTURE.md`
- `docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md`
- `docs/audit/REMEDIATION_STATUS_2026-03-08.md`

Validation minimale:

```bash
git diff --check -- TODO_COCKPIT_OPS.md docs/MCP_AGENTICS_ARCHITECTURE.md \
  docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md \
  docs/audit/REMEDIATION_STATUS_2026-03-08.md
```

## Etat inter-repo

Commits locaux sortis:

- `mascarade`: `e9de1e0`, `1e50bea`, `8291d3e`
- `Kill_LIFE`: `bd49fc6`, `e0b7b17`, `0d61c88`, `b33682a`
- `crazy_life`: `0f8d6ce`, `9205f1a`

Prochain ordre:

1. publier `runtime-core-fixes`
2. publier `ops-observability-followups`
3. publier `docs-state`
4. ne rouvrir aucun chantier technique nouveau tant que cette phase de
   publication n'est pas terminee

## Regle

Ne pas rouvrir un lot technique nouveau tant que cette phase de publication
locale n'est pas terminee.
