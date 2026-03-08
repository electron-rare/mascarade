# Local Change Bundles — 2026-03-08

But: figer l'etat reel de `mascarade` apres publication de la vague
`runtime + ops + docs`, puis consigner les follow-ups operateur deja publies.

## Etat courant

Commits publies:

1. `2c45cf4` — `runtime(core): align canonical python and agent surfaces`
2. `6b2bce9` — `ops(observability): publish runtime and cockpit followups`
3. `51ecbe8` — `docs(state): realign publication and remediation status`
4. `05120b4` — `docs(ops): close observability follow-up state`

Etat reel:

- les checks canoniques de la vague precedente restent verts
- la ligne `MCP/agentics` reste fermee localement
- les follow-ups `operator-surfaces-public-proxy` puis
  `zeroclaw-langgraph-operator-lane` sont publies
- le repo compagnon `finetune/kicad_kic_ai` reste hors bundle `mascarade`

## Lots logiques publies

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

### `zeroclaw-langgraph-operator-lane`

Perimetre:

- vhosts publics proteges pour `zeroclaw.saillant.cc` et
  `langgraph.saillant.cc`
- surfaces publiques `zeroclaw` / `langgraph` dans `OpsHub` et `/api/ops/summary`
- posture explicite `ZeroClaw` on-demand, runbooks `ZeroClaw` / `LangGraph`
  servis meme runtime arrete
- docs/TODOs recales sur cette posture

Checks rejoues pour fermer ce bundle:

- `zeroclaw --version`
- `bash -n ../Kill_LIFE/tools/ai/zeroclaw_*.sh`
- `bash ../Kill_LIFE/tools/ai/zeroclaw_stack_up.sh`
- `curl http://127.0.0.1:3000/health`
- `curl http://127.0.0.1:8788/`
- `bash ../Kill_LIFE/tools/ai/zeroclaw_stack_down.sh`
- `docker compose config -q`
- `cd api && npm run test -- src/routes/ops.test.ts`
- `cd api && npm run build`
- `cd web && npm run build:api-public`
- `cd ../crazy_life && npm run build`
- probes HTTPS `zeroclaw.saillant.cc` / `langgraph.saillant.cc`

Resultat local:

- `zeroclaw --version` -> `0.1.7`
- `zeroclaw.saillant.cc` -> `401` sans auth, `200` avec auth
- `langgraph.saillant.cc` -> `401` sans auth, `200` avec auth
- `/api/ops/summary` authentifie -> `mcp.aggregate_status=ready`, `7/7`
  serveurs `ready`
- `zeroclaw` / `langgraph` remontent comme surfaces publiques `ok=true`

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

### 2. Aucun bundle repo-suivi actif

Les deux follow-ups operateur ont ete publies. Il n'y a plus de delta
repo-suivi `mascarade` actif sur cette ligne.

## Etat inter-repo

Etat courant:

- `mascarade`: vague locale publiee, repo-suivi ferme
- `Kill_LIFE`: repo-suivi ferme; seul `.mascarade/` reste local/exclu
- `crazy_life`: repo-suivi ferme

## Regle

Ne pas rouvrir un lot technique nouveau dans `mascarade` tant qu'un besoin reel
ne requalifie pas un sujet externe ou optionnel.
