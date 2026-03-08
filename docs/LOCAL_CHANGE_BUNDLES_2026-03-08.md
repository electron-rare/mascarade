# Local Change Bundles — 2026-03-08

But: figer l'etat reel de `mascarade` apres publication de la vague
`runtime + ops + docs`, puis suivre le nouveau lot local
`operator-surfaces-public-proxy` avant sa prochaine publication.

## Etat courant

Commits publies:

1. `2c45cf4` — `runtime(core): align canonical python and agent surfaces`
2. `6b2bce9` — `ops(observability): publish runtime and cockpit followups`
3. `51ecbe8` — `docs(state): realign publication and remediation status`
4. `05120b4` — `docs(ops): close observability follow-up state`

Etat reel:

- un nouveau delta repo-suivi local est implemente et valide dans `mascarade`:
  `operator-surfaces-public-proxy`
- les checks canoniques de la vague precedente restent verts
- la ligne `MCP/agentics` reste fermee localement
- le repo compagnon `finetune/kicad_kic_ai` reste hors bundle `mascarade`

Bundle local actif:

### `operator-surfaces-public-proxy`

Perimetre:

- runtime `api` avec `Kill_LIFE` monte en `rw` via `API_RUNTIME_UID`,
  `API_RUNTIME_GID` et `KILL_LIFE_ROOT`
- `edge-proxy` avec vhosts operateur publics proteges pour:
  `Grafana`, `Langfuse`, `Firecrawl`, `Mem0`, `Prometheus`, `Ollama`
- `OpsHub` recale sur les URLs proxifiees canoniques, plus sur des ports bruts
- docs d'etat et TODOs aligns sur cette posture publique avec auth

Checks rejoues pour fermer ce bundle:

- `docker compose config -q`
- `cd api && npm run test -- src/routes/ops.test.ts`
- `cd api && npm run build`
- `cd web && npm run build`
- `GET /api/ops/summary` authentifie
- probes `edge-proxy` avec auth sur `firecrawl`, `mem0`, `prometheus`, `ollama`

Resultat local:

- `/api/ops/summary` authentifie -> `mcp.aggregate_status=ready`, `7/7` serveurs `ready`
- `firecrawl.saillant.cc/mcp` -> `401` sans auth, `400` avec auth attendu
- `mem0.saillant.cc/docs` -> `200` avec auth
- `prometheus.saillant.cc/-/ready` -> `200` avec auth
- `ollama.saillant.cc/api/tags` -> `200` avec auth
- `api` tourne avec `HOME=/tmp`, `KILL_LIFE_ROOT=/workspace/Kill_LIFE` et un montage `rw` actif vers `../Kill_LIFE`

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

### 2. Bundle repo-suivi pret a publier

Le bundle local `operator-surfaces-public-proxy` est ferme techniquement et
pret a etre publie.

## Etat inter-repo

Etat courant:

- `mascarade`: vague locale publiee, repo-suivi ferme
- `Kill_LIFE`: repo-suivi ferme; seul `.mascarade/` reste local/exclu
- `crazy_life`: repo-suivi ferme

## Regle

Ne pas rouvrir un lot technique nouveau dans `mascarade` tant qu'un besoin reel
ne requalifie pas un sujet externe ou optionnel.
