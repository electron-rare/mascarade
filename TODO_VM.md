# TODO — Finalisation VM

Etat relu le `8 mars 2026` sur la stack `mascarade-*` actuellement en service.

## Statut actuel

| Service | Container | Port | Statut |
|---------|-----------|------|--------|
| Mascarade Core | `mascarade-core` | 8100 | OK (`healthy`) |
| Mascarade API | `mascarade-api` | 3100 | OK (`healthy`) |
| Edge Proxy | `mascarade-edge-proxy` | 80 / 443 | OK (`healthy`, bind public) |
| LiteLLM | `mascarade-litellm` | 4000 | OK (`healthy`) |
| Langfuse Web | `mascarade-langfuse` | 3200 | OK (`healthy`) |
| Langfuse Worker | `mascarade-langfuse-worker` | — | OK |
| Firecrawl MCP | `mascarade-firecrawl` | 3400 | OK (`healthy`) |
| Mem0 / OpenMemory | `mascarade-mem0` | 8765 | OK (`healthy`) |
| Industrial Cockpit | `mascarade-agent-factory-cockpit` | 4173 | OK (`healthy`) |
| n8n | `mascarade-n8n` | 5678 | OK (`healthy`) |
| Dify API | `mascarade-dify-api` | 5001 | OK |
| Dify Web | `mascarade-dify-web` | 3500 | OK |
| Dify Worker | `mascarade-dify-worker` | — | OK |
| ClickHouse | `mascarade-clickhouse` | — | OK (`healthy`) |
| Postgres | `mascarade-postgres` | 5432 | OK (`healthy`) |
| Redis | `mascarade-redis` | 6379 | OK (`healthy`) |
| Qdrant | `mascarade-qdrant` | 6333 | OK (`healthy`) |
| Grafana | `mascarade-grafana` | 3001 | OK (`healthy`) |
| Prometheus | `mascarade-prometheus` | 9090 | OK (`healthy`) |
| Tempo | `mascarade-tempo` | 3201 | OK (`healthy`) |
| Blackbox Exporter | `mascarade-blackbox-exporter` | 9115 | OK (`healthy`) |
| SearXNG | `mascarade-searxng` | 8888 | OK (`healthy`) |
| Paperless-ngx | `mascarade-paperless` | 8000 | OK (`healthy`) |
| Karakeep | `mascarade-karakeep` | 3600 | OK (`healthy`) |

Notes:
- L'ancien constat `tools-langfuse KO (ZodError)` ne correspond plus au runtime actuel. `langfuse-web:3000` répond `200` depuis le réseau Docker.
- Les curls host-side vers `127.0.0.1:3200` ne sont pas conclusifs depuis l'environnement sandboxé; la vérification retenue est donc celle faite depuis le réseau Docker et via l'état Docker.
- `Grafana` et `Langfuse` sont maintenant publiables derrière `edge-proxy` sur `grafana.saillant.cc` et `langfuse.saillant.cc`, avec auth dédiée côté proxy.
- `Firecrawl`, `Mem0`, `Prometheus` et `Ollama` sont aussi publiables derrière `edge-proxy` sur `firecrawl.saillant.cc`, `mem0.saillant.cc`, `prometheus.saillant.cc` et `ollama.saillant.cc`, avec la même auth opérateur.
- `Industrial Cockpit` est maintenant publiable derrière `edge-proxy` sur `industrial.saillant.cc`, avec auth opérateur; le cockpit HTTP tourne en service dédié, et les 7 serveurs MCP industriels restent on-demand via stdio depuis `mascarade-core`.
- la surface publique industrielle est vérifiée de bout en bout: `industrial.saillant.cc/` et `industrial.saillant.cc/api/session` répondent `200` avec auth opérateur; aucun port brut n'est publié pour ce cockpit.
- la stack `deploy/phase2` (`SearXNG`, `Paperless-ngx`, `Karakeep`) tourne maintenant en bind local-first sur `127.0.0.1` et remonte correctement derrière `edge-proxy` sur `search.saillant.cc`, `paperless.saillant.cc` et `karakeep.saillant.cc`
- `PLM` expose maintenant un contrat `generic-rest` live-ready dans cette lane industrielle: `/api/industrial/platform` remonte `health` + `contract`, ainsi qu'un statut par opération `live` / `simulated` / `blocked`. Le runtime top-level publie bien la posture canonique `api-key` via `X-API-Key`. Sur cette VM, le sandbox PLM n'est pas encore configuré, donc le runtime courant reste `simulated` sans faux succès live.
- `QMS` expose maintenant la meme posture `generic-rest` live-ready que `PLM`: `/api/industrial/platform` remonte `health` + `contract`, les 3 operations `validation-pack`, `deviation-record` et `qa-signoff`, et la posture d'auth canonique `api-key` via `X-QMS-Key`. Sur cette VM, le sandbox QMS n'est pas encore configure, donc le runtime courant reste `simulated` sans faux succes live.
- `WMS` expose maintenant la meme posture `generic-rest` live-ready que `PLM` et `QMS`, avec auth canonique `api-key` via `X-WMS-Key`, 3 operations (`pick-wave`, `shipment-release`, `inventory-hold`) et visibilite `health` + `contract` dans `/api/industrial/platform`; sur cette VM, le runtime reste volontairement `simulated` tant que le sandbox WMS n'est pas configure
- `DCS` dispose maintenant d'un sandbox OT gouverne local, raccorde a la lane industrielle, avec un flux de demo explicite sans faux write direct
- `ZeroClaw` est maintenant installe nativement sur la VM (`zeroclaw 0.1.7`), avec un runtime operateur demarrable a la demande via `Kill_LIFE/tools/ai/zeroclaw_stack_up.sh`.
- `zeroclaw.saillant.cc` sert maintenant la surface live `ZeroClaw` derriere `edge-proxy`, avec fallback offline propre si le runtime est arrete.
- `zeroclaw-docs.saillant.cc` et `langgraph.saillant.cc` servent les runbooks operateur authentifies.
- Un smoke reel `POST /webhook` repond maintenant `200` via `OpenRouter`, avec une reponse modele validee de bout en bout.
- Le bind hôte de `edge-proxy` est maintenant `0.0.0.0`; le certificat réel Let's Encrypt est installé via DNS-01 Cloudflare avec couverture `saillant.cc` + `*.saillant.cc`.

## TODO priorisés

### Bloquant
- [x] `Langfuse` ne crashe plus et répond sur le réseau Docker.
- [x] Ajouter un `healthcheck` Docker explicite sur `mascarade-langfuse`.
- [x] Recréer `langfuse-web` pour matérialiser le nouveau statut `healthy` dans `docker ps`.
- [x] `Langfuse` retenu comme brique supportée, optionnelle hors profil standard sur VM légère.
- [x] `Tempo` branché comme backend de traces nominal.
- [x] `Grafana` et `Langfuse` sont atteignables via le proxy opérateur.
- [x] `Firecrawl`, `Mem0`, `Prometheus` et `Ollama` sont atteignables via le proxy opérateur.
- [x] `Industrial Cockpit` est atteignable via le proxy opérateur.
- [x] `ZeroClaw` live, `ZeroClaw` docs et `LangGraph` sont visibles comme surfaces opérateur proxifiées.
- [x] Le runtime `ZeroClaw` se demarre et s'arrete proprement a la demande via les scripts `Kill_LIFE`.
- [x] Le fallback provider `OpenRouter` est configure et valide sur un appel modele reel via le gateway natif.

### Sécurité
- [x] `MASCARADE_API_KEY` est renseignée dans `/home/clems/mascarade/.env`; l'auth n'est pas désactivée en pratique.
- [ ] Garder la règle: ne jamais régénérer un `.env` de VM avec `MASCARADE_API_KEY` vide.
- [x] `OPENAI_API_KEY` est configurée et validée par un smoke strict `provider=openai`.
- [x] `ANTHROPIC_API_KEY` est configurée dans la VM.
- [ ] Lever le blocage billing `Anthropic` pour valider `claude` en strict.
- [x] `GOOGLE_API_KEY` est configurée avec `GOOGLE_AUTH_MODE=api_key`.
- [ ] Activer `generativelanguage.googleapis.com` sur le projet Google associé pour valider `google` en strict.
- [x] `MISTRAL_API_KEY` est déjà configurée.
- [x] `OPENROUTER_API_KEY` est configurée dans le runtime natif `ZeroClaw`.
- [x] `Notion` est sorti du scope actif; ne plus traiter `NOTION_*` comme secrets à compléter sur cette VM.

### Infra
- [x] Source `Firecrawl` retenue: image officielle `mcp/firecrawl@sha256:e6676bd31d1806574d931b7a7b7b6fba953c031853e80adc1ec8115c17ab81ca`.
- [x] Intégration repo `Firecrawl` prête dans la stack Mascarade.
- [x] `FIRECRAWL_API_KEY` configurée sur la VM.
- [x] `mascarade-firecrawl` démarré et `healthy` sur le port `3400`.
- [x] Déployer `Mem0` avec une cible réelle.
  - Cible retenue: `mem0/openmemory-mcp`.
  - Runtime valide sur la VM: `mascarade-mem0` est `healthy`.
  - Cablage actif sur `Qdrant` + `LiteLLM` (OpenAI-compatible).
- [x] `Docling` est importable dans le venv tools.
- [x] `openai-whisper` est importable dans le venv tools.
- [x] La stack `deploy/phase2` est déployée sur la VM.
  - `SearXNG` sain sur `mascarade-searxng`.
  - `Paperless-ngx` sain sur `mascarade-paperless`.
  - `Karakeep` sain sur `mascarade-karakeep`.

### Réseau
- [x] Le reverse proxy HTTPS existe déjà via `edge-proxy`.
- [x] `edge-proxy` est maintenant publié sur `0.0.0.0:80/443`.
- [x] `Grafana` et `Langfuse` ont un routage dédié derrière `edge-proxy`.
- [x] `Firecrawl`, `Mem0`, `Prometheus` et `Ollama` ont un routage dédié derrière `edge-proxy`.
- [x] `Industrial Cockpit` a un routage dédié derrière `edge-proxy`.
- [x] `ZeroClaw` live, `ZeroClaw` docs et `LangGraph` ont un routage dédié derrière `edge-proxy`.
- [x] `SearXNG`, `Paperless-ngx` et `Karakeep` ont un routage dédié derrière `edge-proxy`.
- [x] Une auth opérateur dédiée protège ces surfaces côté proxy.
- [x] Le certificat auto-signé de fallback couvre maintenant `saillant.cc`, `grafana.saillant.cc`, `langfuse.saillant.cc` et `dify.saillant.cc`.
- [x] Certificat réel Let's Encrypt installé via ACME DNS-01 Cloudflare.
- [x] Couverture wildcard active: `saillant.cc` et `*.saillant.cc`.

### Monitoring
- [x] `Langfuse` est connecté à `Mascarade` pour tracer les appels LLM.
- [x] Des dashboards Grafana couvrent `Langfuse`, `n8n`, `Dify`, `LiteLLM` et la posture tooling/observability.
- [x] `Prometheus` scrape les endpoints natifs et les probes HTTP via `blackbox-exporter`.
- [x] `Tempo` est branché sur l'OTel Collector et visible dans Grafana.

### Mac local
- [x] Un bootstrap MCP Mac est maintenant scripté dans `Kill_LIFE` via `tools/bootstrap_mac_mcp.sh`.
- [x] `Playwright MCP` est intégré à ce bootstrap.
- [x] Bootstrap `Codex` exécuté avec succès sur le Mac opérateur réel via `bash tools/bootstrap_mac_mcp.sh codex --apply`.
- [x] Les serveurs MCP attendus sont visibles dans `codex mcp list`: `kicad`, `validate-specs`, `knowledge-base`, `github-dispatch`, `freecad`, `openscad`, `huggingface`, `playwright`.
- [x] `Playwright MCP` est validé sur le Mac cible via `npx -y @playwright/mcp@latest --help`.

## Restes reels

Les restes encore ouverts ne sont plus des blocs locaux d'implementation:

- `Anthropic`: cle presente mais credit insuffisant sur l'API
- `Google Gemini`: cle presente mais `generativelanguage.googleapis.com` est desactive sur le projet associe
- sur le Mac cible, le worktree `/Users/electron/mascarade` reste dirty; ne pas faire de `git pull` tant que les changements locaux ne sont pas consolides
- si le sandbox `PLM` doit passer en live, il faut encore renseigner `AGENT_FACTORY_PLM_BASE_URL`, `AGENT_FACTORY_PLM_API_KEY` et les `AGENT_FACTORY_PLM_RESOURCE_*` sur la VM
- si le sandbox `QMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_QMS_BASE_URL`, `AGENT_FACTORY_QMS_API_KEY` et les `AGENT_FACTORY_QMS_RESOURCE_*` sur la VM
- si le sandbox `WMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_WMS_BASE_URL`, `AGENT_FACTORY_WMS_API_KEY` et les `AGENT_FACTORY_WMS_RESOURCE_*` sur la VM
- `DCS` est ferme localement sur un sandbox/runtime OT gouverne et un flux de demo executable; ne rouvrir un vrai DCS live qu'avec un runtime/contrat OT externe

## Automation locale

Chemin canonique pour reprendre automatiquement le prochain lot utile:

```bash
cd /home/clems/mascarade
bash scripts/run_next_useful_lot.sh
  # enchaînement automatique (3 lots maxi) :
  # bash scripts/run_next_useful_lot.sh --chain
```

Commandes fines:

```bash
bash scripts/next_useful_lot.sh detect
bash scripts/next_useful_lot.sh checks
bash scripts/next_useful_lot.sh state --write
```

## Infra existante sur la VM

| Service | Container | Port |
|---------|-----------|------|
| Ollama | `mascarade-ollama` | 11434 |
| Qdrant | `mascarade-qdrant` | 6333 |
| Redis | `mascarade-redis` | 6379 |
| Postgres | `mascarade-postgres` | 5432 |
| Grafana | `mascarade-grafana` | 3001 |
| Prometheus | `mascarade-prometheus` | 9090 |
| Tempo | `mascarade-tempo` | 3201 |
| Blackbox Exporter | `mascarade-blackbox-exporter` | 9115 |
| Industrial Cockpit | `mascarade-agent-factory-cockpit` | 4173 |
| SearXNG | `mascarade-searxng` | 8888 |
| Paperless-ngx | `mascarade-paperless` | 8000 |
| Karakeep | `mascarade-karakeep` | 3600 |

## Fichiers clés

```text
/home/clems/mascarade/.env
/home/clems/mascarade/docker-compose.yml
/home/clems/mascarade/TODO_VM.md
```
