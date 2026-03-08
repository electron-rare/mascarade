# Local Change Bundles — 2026-03-08

But: figer le residuel local de `mascarade` en lots de commit explicites, puis
enchaîner proprement vers `Kill_LIFE` et `crazy_life`.

## Etat courant

Commits locaux deja sortis:

1. `e9de1e0` — `mcp-runtime-surfaces`
2. `1e50bea` — `ops-observability-runtime`

Etat residuel:

- un seul bundle `mascarade` reste ouvert: `docs-state`
- `finetune-followups` n'a plus de delta local a sortir
- le prochain travail n'est plus technique; c'est de la consolidation/
  publication

## Bundle restant — `docs-state`

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

## Ordre inter-repo recommande

1. finir `mascarade:docs-state`
2. sortir `Kill_LIFE:mcp-runtime`
3. sortir `Kill_LIFE:cad-mcp`
4. sortir `Kill_LIFE:python-local`
5. sortir `crazy_life:cockpit runtime alignment`
6. sortir `crazy_life:docs state`

## Regle

Ne pas rouvrir un lot technique nouveau tant que cette phase de publication
locale n'est pas terminee.
