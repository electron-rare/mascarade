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
- le follow-up `industrial-mcp-operator-lane` est maintenant publie aussi; il
  etend la posture operateur publique au cockpit industriel
  `agent-factory-cockpit`
- les follow-ups `industrial-plm-generic-rest` et
  `industrial-qms-generic-rest` sont maintenant publies; ils etendent la lane
  industrielle avec la posture `generic-rest` live-ready sur `PLM` et `QMS`,
  sans faux vert `live` tant que la VM ne porte pas les sandboxes
  correspondantes
- le follow-up `industrial-wms-generic-rest` est maintenant publie; il aligne
  `WMS` sur la meme posture `generic-rest` live-ready que `PLM` et `QMS`,
  sans faux vert `live` tant que la VM ne porte pas le sandbox WMS
- le follow-up `phase2-operator-stack` est maintenant publie; il ajoute la
  stack documentaire/recherche `SearXNG` / `Paperless-ngx` / `Karakeep` en
  bind local-first, plus les surfaces publiques protegees
  `search.saillant.cc`, `paperless.saillant.cc` et `karakeep.saillant.cc`
- le repo compagnon `finetune/kicad_kic_ai` reste hors bundle `mascarade`
- le follow-up `industrial-dcs-governed-sandbox` est maintenant ferme
  localement; il publie un sandbox OT gouverne, l'integre a la lane
  industrielle et ajoute un flux de demo explicite sans write direct

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

### `industrial-mcp-operator-lane`

Perimetre:

- service `agent-factory-cockpit` ajoute a la stack `mascarade`
- montage `../agent-factory-cockpit` en lecture seule dans `mascarade-core` pour
  permettre la decouverte et les appels stdio des 7 serveurs MCP industriels
- hostname public protege `industrial.saillant.cc` derriere `edge-proxy`
- surfaces `/api/industrial/*`, `monitor.public.surfaces`, `/api/ops/summary`
  et `OpsHub` etendues au cockpit industriel et a l'inventaire serveur
- miroir cockpit `crazy_life` aligne sur la meme posture

Checks rejoues pour fermer ce bundle:

- `docker compose config -q`
- `cd api && npm run test -- src/routes/industrial.test.ts src/routes/ops.test.ts`
- `cd api && npm run build`
- `cd web && npm run build:api-public`
- `cd ../crazy_life && npm run build`
- `docker compose up -d --build core api edge-proxy agent-factory-cockpit`
- `GET /api/industrial/platform` authentifie
- `GET /api/ops/summary` authentifie
- probe HTTPS `industrial.saillant.cc` sans auth puis avec auth

Resultat local:

- `Host: industrial.saillant.cc` sur le proxy local -> `401` sans auth, `200` avec auth
- `Host: industrial.saillant.cc` sur `/api/session` -> `200` avec auth
- `/api/industrial/platform` -> inventaire `cockpit-ops`, `plm`, `qms`, `mes`,
  `erp`, `wms`, `dcs`
- `/api/ops/summary` -> surface publique `industrial` visible, avec resume
  runtime des 7 serveurs
- `/api/ops/summary` -> `industrial.ui.ok=true`, `cockpit_service_ok=true`,
  `cockpit_proxy_ok=true`
- `OpsHub` n'utilise plus aucun port brut pour ce cockpit

### `phase2-operator-stack`

Perimetre:

- ajout de `deploy/phase2` avec `SearXNG`, `Paperless-ngx` et `Karakeep`
- bind local-first sur `127.0.0.1` et raccord au reseau
  `mascarade_mascarade-network`
- vhosts publics proteges `search.saillant.cc`, `paperless.saillant.cc` et
  `karakeep.saillant.cc` derriere `edge-proxy`
- surfaces publiques `search`, `paperless` et `karakeep` ajoutees dans
  `/api/ops/monitor`, `/api/ops/summary`, `OpsHub` et `ops-console`
- miroir `crazy_life` aligne sur les memes liens proxifies

Checks rejoues pour fermer ce bundle:

- `cd /home/clems/mascarade/deploy/phase2 && docker compose --env-file .env -f docker-compose.yml config -q`
- `cd /home/clems/mascarade/deploy/phase2 && docker compose --env-file .env -f docker-compose.yml up -d`
- `cd /home/clems/mascarade && docker compose up -d --build api edge-proxy`
- `cd /home/clems/mascarade && npm --prefix api run build`
- `cd /home/clems/mascarade && npm --prefix web run build:api-public`
- `cd /home/clems/crazy_life && npm run build`
- `GET /api/ops/monitor` authentifie

Resultat local:

- `mascarade-searxng`, `mascarade-paperless` et `mascarade-karakeep` sont
  `healthy`
- `/api/ops/monitor` -> `search.ok=true`, `paperless.ok=true`,
  `karakeep.ok=true`
- `search.saillant.cc` -> `200` avec auth
- `paperless.saillant.cc` -> `302` avec auth attendu
- `karakeep.saillant.cc` -> `307` avec auth attendu
- `deploy/phase2/.env` reste hors Git; seule `.env.example` est versionnee

## Reliquats locaux

### 0. Follow-ups publies `industrial-plm-generic-rest` / `industrial-qms-generic-rest`

Perimetre:

- `agent-factory-cockpit`: ressources MCP `plm://contract` et
  `qms://contract`, topologies `plm` / `qms` sorties du statut `blocked`,
  docs/runtime recales sur la posture `generic-rest` `api-key` avec fallback
  explicite
- `mascarade`: enrichissement `/api/industrial/platform` et `/api/ops/summary`
  pour faire remonter `health` + `contract` sur les serveurs industriels, plus
  recapitulatif industriel plus riche dans `OpsHub` et `Infrastructure`
- `crazy_life`: aucun miroir code additionnel requis; le rendu existant couvre
  deja la posture enrichie via le payload proxifie canonique

Checks rejoues:

- `cd /home/clems/agent-factory-cockpit && python3 -m unittest tests.test_topology tests.test_execution tests.test_mcp tests.test_validation -q`
- `cd /home/clems/mascarade/api && npm run test -- src/routes/industrial.test.ts src/routes/ops.test.ts`
- `cd /home/clems/mascarade/api && npm run build`
- `cd /home/clems/mascarade/web && npm run build:api-public`
- `cd /home/clems/crazy_life && npm run build`
- `cd /home/clems/mascarade && docker compose config -q`
- `cd /home/clems/mascarade && docker compose up -d --build core api edge-proxy agent-factory-cockpit`
- `GET /api/industrial/platform` authentifie
- `GET /api/ops/summary` authentifie
- probe `Host: industrial.saillant.cc` -> `401` sans auth, `200` avec auth

Etat local:

- `plm` expose bien `health` + `contract` dans `/api/industrial/platform`
- `qms` expose bien `health` + `contract` sur le meme modele
- les contrats `PLM` et `QMS` sont `live-ready` au niveau dossier/runtime, mais
  restent `incomplete` faute d'attachement OpenAPI/Postman
- la VM ne porte pas encore de config sandbox `PLM` / `QMS`, donc le runtime
  courant remonte `simulated` et non `live`
- `industrial.saillant.cc` repond `401` sans auth et `200` avec auth; le
  recapitulatif industriel publie bien `7` serveurs `runtime_ok`

### 0c. Follow-up publie `industrial-wms-generic-rest`

Perimetre:

- `agent-factory-cockpit`: contrat `wms-generic-enterprise` a remplir avec auth
  `api-key`, header canonique `X-WMS-Key`, ressources `pick-wave`,
  `shipment-release` et `inventory-hold`, et posture runtime live-ready
- `mascarade`: verification du rendu `wms` dans `/api/industrial/platform` et
  `/api/ops/summary`, sans nouvelle logique dediee si la lane industrielle
  existante suffit
- `crazy_life`: pas de nouveau code prevu tant que le miroir industriel generic
  absorbe deja le statut enrichi

Checks rejoues:

- `cd /home/clems/agent-factory-cockpit && python3 -m unittest tests.test_topology tests.test_execution tests.test_mcp tests.test_validation -q`
- `cd /home/clems/mascarade/api && npm run test -- src/routes/industrial.test.ts src/routes/ops.test.ts`
- `cd /home/clems/mascarade/api && npm run build`
- `cd /home/clems/mascarade/web && npm run build:api-public`
- `cd /home/clems/crazy_life && npm run build`
- `GET /api/industrial/platform` authentifie

Etat local:

- `wms` expose `health` + `contract` dans `/api/industrial/platform`
- `wms` remonte `ok=true` et `runtime_ok=true` dans l'inventaire industriel et
  dans `/api/ops/summary`
- le pack `WMS` est `live-ready` au niveau contrat/runtime, avec auth
  canonique `api-key` via `X-WMS-Key`
- le dossier `WMS` reste `incomplete` faute d'attachement OpenAPI/Postman,
  comme `PLM` et `QMS`
- la VM reste `simulated` tant que la sandbox WMS n'est pas configuree

### 1. Repo compagnon `finetune/kicad_kic_ai`

- ce repo reste opere comme un companion repo independant
- il ne fait plus partie des bundles `mascarade`
- le parent ignore maintenant son dirty state via `ignore = dirty` dans
  `.gitmodules`

Ce que cela signifie:

- un changement dans `finetune/kicad_kic_ai` doit etre gere et publie depuis ce
  repo compagnon
- il ne doit pas rouvrir artificiellement un chantier dans `mascarade`

### 2. Bundles repo-suivis restants
Les follow-ups operateur deja publies restent:

- `operator-surfaces-public-proxy`
- `zeroclaw-langgraph-operator-lane`
- `industrial-mcp-operator-lane`
- `industrial-plm-generic-rest`
- `industrial-qms-generic-rest`
- `phase2-operator-stack`

Le seul bundle repo-suivi actif de cette ligne est maintenant: aucun.

## Etat inter-repo

Etat courant:

- `mascarade`: repo-suivi ferme; les follow-ups industriels `PLM/QMS/WMS` sont publies
- `Kill_LIFE`: repo-suivi ferme; seul `.mascarade/` reste local/exclu
- `crazy_life`: aucun miroir local actif; le rendu industriel actuel reste generique

## Regle

Ne pas rouvrir un lot technique nouveau dans `mascarade` tant qu'un besoin reel
ne requalifie pas un sujet externe ou optionnel.

Chemin d'automatisation court terme:

```bash
cd /home/clems/mascarade
bash scripts/next_useful_lot.sh detect
bash scripts/next_useful_lot.sh checks
bash scripts/next_useful_lot.sh state --write
```

Le fichier versionne [NEXT_USEFUL_LOT_STATE.md](/home/clems/mascarade/docs/NEXT_USEFUL_LOT_STATE.md)
sert de handoff court terme pour le lot actif.
