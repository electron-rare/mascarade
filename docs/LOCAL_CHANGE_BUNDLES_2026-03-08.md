# Local Change Bundles — 2026-03-08

But: clore le reliquat local de `mascarade` en gardant une cartographie
historique lisible des lots deja sortis au `2026-03-08`.

## Etat courant

Commits locaux deja sortis:

1. `e9de1e0` — `mcp-runtime-surfaces`
2. `1e50bea` — `ops-observability-runtime`
3. `8291d3e` — `docs-state`

Etat courant:

- `mascarade` ne porte plus qu'un lot de cloture doc/etat, plus un ajustement
  de dashboard Grafana
- `Kill_LIFE` reste propre cote suivi Git; seul `.mascarade/` reste local/exclu
- `crazy_life` est propre
- le prochain travail n'est plus de rouvrir la pile `MCP/agentics`; c'est de
  garder les sujets externes ou optionnels hors du repo courant

Checks canoniques rejoues avec succes sur `mascarade`:

- `bash scripts/test_python.sh --bootstrap --venv-dir /tmp/mascarade-plan-impl-2`
- `cd api && npm run build`
- `cd web && npm run build`
- `docker compose config -q`
- `GET /api/ops/summary` authentifie -> `mcp.aggregate_status=ready`, `7/7`
  serveurs `ready`

Reliquats suivis actuels:

1. `docs-state-followup`
2. `finetune/kicad_kic_ai` reste dirty dans le repo imbrique et n'entre pas
   dans le bundle `mascarade` courant

## Bundle `docs-state-followup`

Objet:

- realigner les TODO/plans/documents d'etat sur le runtime reel final du lot
  observabilite/proxy
- clore la cartographie des bundles ouverts dans `mascarade`
- corriger le panneau Grafana restant sur une metrique effectivement exposee

Fichiers:

- `README.md`
- `TODO_VM.md`
- `TODO_COCKPIT_OPS.md`
- `TODO_IMPLEMENTE.md`
- `deploy/grafana/provisioning/dashboards/json/mascarade-tooling-observability.json`
- `docs/EXECUTION_PLAN_2026-03-07.md`
- `docs/MCP_AGENTICS_ARCHITECTURE.md`
- `docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md`
- `docs/audit/REMEDIATION_STATUS_2026-03-08.md`

Validation minimale:

```bash
python3 -c 'import json; json.load(open("deploy/grafana/provisioning/dashboards/json/mascarade-tooling-observability.json"))'
git diff --check -- README.md TODO_VM.md TODO_COCKPIT_OPS.md TODO_IMPLEMENTE.md \
  deploy/grafana/provisioning/dashboards/json/mascarade-tooling-observability.json \
  docs/EXECUTION_PLAN_2026-03-07.md docs/MCP_AGENTICS_ARCHITECTURE.md \
  docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md \
  docs/audit/REMEDIATION_STATUS_2026-03-08.md
```

## Etat inter-repo

Commits locaux sortis:

- `mascarade`: `e9de1e0`, `1e50bea`, `8291d3e`
- `Kill_LIFE`: `bd49fc6`, `e0b7b17`, `0d61c88`, `b33682a`
- `crazy_life`: `0f8d6ce`, `9205f1a`

Prochain ordre:

1. sortir `docs-state-followup`
2. ne rouvrir aucun chantier technique nouveau tant qu'aucun besoin concret ne
   le justifie
3. garder les sujets externes (`DNS/ACME`, secrets providers, setup Mac)
   hors de ce repo tant qu'ils ne sont pas explicitement ouverts

## Regle

Ne pas rouvrir un lot technique nouveau tant qu'un besoin reel ne requalifie
pas les restes externes ou optionnels.
