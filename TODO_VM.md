# TODO — Finalisation VM

Etat relu le `8 mars 2026` sur la stack `mascarade-*` actuellement en service.

## Statut actuel

| Service | Container | Port | Statut |
|---------|-----------|------|--------|
| Mascarade Core | `mascarade-core` | 8100 | OK (`healthy`) |
| Mascarade API | `mascarade-api` | 3100 | OK (`healthy`) |
| Edge Proxy | `mascarade-edge-proxy` | 80 / 443 | OK (`healthy`, bind loopback) |
| LiteLLM | `mascarade-litellm` | 4000 | OK (`healthy`) |
| Langfuse Web | `mascarade-langfuse` | 3200 | OK (`healthy`) |
| Langfuse Worker | `mascarade-langfuse-worker` | — | OK |
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

Notes:
- L'ancien constat `tools-langfuse KO (ZodError)` ne correspond plus au runtime actuel. `langfuse-web:3000` répond `200` depuis le réseau Docker.
- Les curls host-side vers `127.0.0.1:3200` ne sont pas conclusifs depuis l'environnement sandboxé; la vérification retenue est donc celle faite depuis le réseau Docker et via l'état Docker.

## TODO priorisés

### Bloquant
- [x] `Langfuse` ne crashe plus et répond sur le réseau Docker.
- [x] Ajouter un `healthcheck` Docker explicite sur `mascarade-langfuse`.
- [x] Recréer `langfuse-web` pour matérialiser le nouveau statut `healthy` dans `docker ps`.
- [ ] Trancher si `Langfuse` reste une brique supportée ou redevient un service `heavy` optionnel seulement.

### Sécurité
- [x] `MASCARADE_API_KEY` est renseignée dans `/home/clems/mascarade/.env`; l'auth n'est pas désactivée en pratique.
- [ ] Garder la règle: ne jamais régénérer un `.env` de VM avec `MASCARADE_API_KEY` vide.
- [ ] Compléter les secrets opérateurs encore absents dans `.env` selon le besoin réel:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `NOTION_TOKEN`
- [x] `MISTRAL_API_KEY` est déjà configurée.

### Infra
- [ ] Déployer `Firecrawl` avec une source publiable réelle.
  - Contrainte actuelle: `ghcr.io/mendableai/firecrawl:latest` privée.
  - Options restantes: image Docker Hub compatible ou build depuis le repo source.
- [ ] Déployer `Mem0` avec une cible réelle.
  - L'image `mem0ai/mem0` n'est pas disponible telle quelle.
  - Options restantes: venv Python dédié (`mem0ai`) ou `openmemory-mcp`.
- [ ] Installer `Docling` dans le venv tools.
- [ ] Installer `openai-whisper` dans le venv tools.

### Réseau
- [x] Le reverse proxy HTTPS existe déjà via `edge-proxy`.
- [x] Les binds HTTP/HTTPS restent limités à `127.0.0.1`.
- [ ] Si exposition externe voulue: publier `edge-proxy` hors loopback et finaliser le chemin ACME/DNS réellement utilisé.

### Monitoring
- [ ] Connecter `Langfuse` à `Mascarade` pour tracer les appels LLM.
- [ ] Ajouter des dashboards Grafana pour `Langfuse`, `n8n`, `Dify`, `LiteLLM`.
- [ ] Ajouter ou documenter les endpoints Prometheus réellement scrapeables pour les services exposés.

### Mac local
- [ ] Installer les serveurs MCP utiles côté Mac.
- [ ] Installer `Playwright MCP` côté Mac.

## Infra existante sur la VM

| Service | Container | Port |
|---------|-----------|------|
| Ollama | `mascarade-ollama` | 11434 |
| Qdrant | `mascarade-qdrant` | 6333 |
| Redis | `mascarade-redis` | 6379 |
| Postgres | `mascarade-postgres` | 5432 |
| Grafana | `mascarade-grafana` | 3001 |
| Prometheus | `mascarade-prometheus` | 9090 |

## Fichiers clés

```text
/home/clems/mascarade/.env
/home/clems/mascarade/docker-compose.yml
/home/clems/mascarade/TODO_VM.md
```
