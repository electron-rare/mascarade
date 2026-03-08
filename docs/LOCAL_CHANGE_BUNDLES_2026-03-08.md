# Local Change Bundles — 2026-03-08

But: figer l'etat reel de `mascarade` apres publication de la vague
`runtime + ops + docs`, puis documenter les seuls restes locaux hors
repo-suivi.

## Etat courant

Commits publies:

1. `2c45cf4` — `runtime(core): align canonical python and agent surfaces`
2. `6b2bce9` — `ops(observability): publish runtime and cockpit followups`
3. `51ecbe8` — `docs(state): realign publication and remediation status`
4. `05120b4` — `docs(ops): close observability follow-up state`

Etat reel:

- aucun delta repo-suivi actif ne reste a sortir dans `mascarade`
- les checks canoniques restent verts
- la ligne `MCP/agentics` est fermee localement
- le seul reliquat visible hors repo-suivi est le repo compagnon
  `finetune/kicad_kic_ai`

Checks canoniques rejoues avec succes:

- `bash scripts/test_python.sh --bootstrap --venv-dir /tmp/mascarade-plan-impl-2`
- `cd api && npm run test -- src/routes/ops.test.ts`
- `cd api && npm run build`
- `cd web && npm run build:api-public`
- `docker compose config -q`
- `GET /api/ops/summary` authentifie -> `mcp.aggregate_status=ready`, `7/7`
  serveurs `ready`
- `POST /api/ops/mcp/probe/freecad?force=true` -> `ready`

## Reliquats locaux

### 1. Repo compagnon `finetune/kicad_kic_ai`

- ce repo reste opere comme un companion repo independant
- il ne fait plus partie des bundles `mascarade`
- le parent ignore maintenant son dirty state via `ignore = dirty` dans
  `.gitmodules`

Ce que cela signifie:

- un changement dans `finetune/kicad_kic_ai` doit etre gere et publie depuis ce
  repo compagnon
- il ne doit pas rouvrir artificiellement un chantier dans `mascarade`

### 2. Aucun bundle repo-suivi ouvert

Il n'y a plus de bundle local a couper dans `mascarade`.

## Etat inter-repo

Etat courant:

- `mascarade`: vague locale publiee, repo-suivi ferme
- `Kill_LIFE`: repo-suivi ferme; seul `.mascarade/` reste local/exclu
- `crazy_life`: repo-suivi ferme

## Regle

Ne pas rouvrir un lot technique nouveau dans `mascarade` tant qu'un besoin reel
ne requalifie pas un sujet externe ou optionnel.
