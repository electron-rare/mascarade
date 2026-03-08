# Local Change Bundles — 2026-03-08

But: figer le residuel local de `mascarade` en lots de commit explicites, puis
enchaîner proprement vers `Kill_LIFE` et `crazy_life`.

## Etat courant

Commits locaux deja sortis:

1. `e9de1e0` — `mcp-runtime-surfaces`
2. `1e50bea` — `ops-observability-runtime`
3. `8291d3e` — `docs-state`

Etat residuel:

- aucun bundle `mascarade` n'est encore ouvert
- `Kill_LIFE` et `crazy_life` ont eux aussi leurs commits locaux de consolidation
- le prochain travail n'est plus technique; c'est `checks finaux + decision de publication distante`

## Bundle `docs-state`

Objet:

- realigner les TODO/plans/documents d'etat sur le runtime reel
- figer la cartographie des bundles et le statut de remediations fermees
- documenter le passage en phase de publication multi-repo

Fichiers:

- `TODO_COCKPIT_OPS.md`
- `TODO_IMPLEMENTE.md`
- `docs/EXECUTION_PLAN_2026-03-07.md`
- `docs/MCP_AGENTICS_ARCHITECTURE.md`
- `docs/audit/REMEDIATION_STATUS_2026-03-08.md`
- `docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md`
- `scripts/review_local_change_bundle.sh`

Validation minimale:

```bash
git diff --check -- TODO_COCKPIT_OPS.md TODO_IMPLEMENTE.md \
  docs/EXECUTION_PLAN_2026-03-07.md docs/MCP_AGENTICS_ARCHITECTURE.md \
  docs/audit/REMEDIATION_STATUS_2026-03-08.md \
  docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md \
  scripts/review_local_change_bundle.sh
```

Commit recommande:

```bash
git add TODO_COCKPIT_OPS.md TODO_IMPLEMENTE.md \
  docs/EXECUTION_PLAN_2026-03-07.md docs/MCP_AGENTICS_ARCHITECTURE.md \
  docs/audit/REMEDIATION_STATUS_2026-03-08.md \
  docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md \
  scripts/review_local_change_bundle.sh
git commit -m "docs(state): realign plans and local bundle map"
```

## Etat inter-repo

Commits locaux sortis:

- `mascarade`: `e9de1e0`, `1e50bea`, `8291d3e`
- `Kill_LIFE`: `bd49fc6`, `e0b7b17`, `0d61c88`, `b33682a`
- `crazy_life`: `0f8d6ce`, `9205f1a`

Prochain ordre:

1. rejouer les checks minimaux par repo
2. decider du push repo par repo
3. laisser les restes externes/optionnels hors de cette phase

## Regle

Ne pas rouvrir un lot technique nouveau tant que cette phase de publication
locale n'est pas terminee.
