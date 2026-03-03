# TODO — Finalisation VM (192.168.0.119)

## Statut actuel

| Service | Container | Port | Statut |
|---------|-----------|------|--------|
| Mascarade Core | mascarade-core-1 | 8100 | OK |
| Mascarade API | mascarade-api-1 | 3100 | OK |
| ClickHouse | tools-clickhouse | — | OK |
| Langfuse | tools-langfuse | 3200 | KO (ZodError) |
| n8n | tools-n8n | 5678 | OK |
| LiteLLM | tools-litellm | 4000 | OK |
| Dify API | tools-dify-api | 5001 | OK |
| Dify Web | tools-dify-web | 3500 | OK |
| Dify Worker | tools-dify-worker | — | OK |

---

## A faire

### 1. Fixer Langfuse
- [ ] Le container ne crash plus mais le health endpoint ne répond pas (toujours KO)
- [ ] Erreur : `TypeError: Cannot set property message of ZodError which has only a getter`
- [ ] Env vars ajoutées : `ENCRYPTION_KEY`, `REDIS_HOST/PORT`, `LANGFUSE_S3_EVENT_UPLOAD_ENABLED=false`
- [x] Piste testée : version spécifique `3.50.0` (KO aussi)
- [x] Décision machine légère : service désactivé par défaut (profile `heavy`)
- [ ] Fichier : `~/tools/docker-compose.yml`

### 2. Configurer les clés API
- [ ] Remplir les vraies clés dans `/mascarade/.env` sur la VM
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `MISTRAL_API_KEY`
  - `NOTION_TOKEN`
- [x] Copier/linker le `.env` pour `~/tools/` (LiteLLM, Dify en ont besoin) — synchronisation effectuée
- [x] Restart mascarade + tools après

### 3. Déployer Firecrawl
- [ ] L'image `ghcr.io/mendableai/firecrawl:latest` est privée (denied)
- [ ] Alternative : `mendableai/firecrawl` sur Docker Hub ou build depuis le repo GitHub
- [x] Port prévu : 3400
- [ ] Utilise Redis existant (`zacus-redis:6379/2`)

### 4. Déployer Mem0
- [ ] L'image `mem0ai/mem0` n'existe pas sur Docker Hub
- [ ] Alternative 1 : installer via pip (`pip install mem0ai`) dans un venv Python sur la VM
- [ ] Alternative 2 : utiliser `openmemory-mcp` (le repo officiel Mem0)
- [x] Port prévu : 3300
- [ ] Utilise Qdrant existant (`zacus-qdrant:6333`)

### 5. Installer les outils Python
- [x] Créer un venv dans `~/tools/python-tools/`
- [x] **GraphRAG** (`pip install graphrag`) — installé dans `~/tools/python-tools/.venv`
- [ ] **Docling** (`pip install docling`) — résolution de dépendances très longue / interrompue
- [ ] **Whisper** (`pip install openai-whisper`) — inclus dans la tentative globale interrompue

### 6. Ajouter deps Mascarade
- [x] **CrewAI** — ajouté dans `core/pyproject.toml`, skill d'orchestration ajouté
- [x] **OpenAI Agents SDK** — ajouté comme dépendance
- [x] Rebuild image Docker mascarade après

### 7. Configurer MCP Servers (local Mac)
- [ ] Installer `@anthropic-ai/mcp` et serveurs MCP utiles (à faire sur Mac)
- [ ] Playwright MCP pour le scraping navigateur (à faire sur Mac)
- [x] Connecter Claude Code aux MCP servers via `~/.claude/settings.json` (config locale VM prête)

### 8. Sécuriser les accès
- [x] Tous les ports Mascarade/Tools ajoutés sont en `127.0.0.1` (local uniquement)
- [ ] Mettre en place un reverse proxy (Caddy/nginx) pour exposer avec HTTPS
- [x] Activer l'auth Bearer sur Mascarade (`MASCARADE_API_KEY` dans `.env`)
- [x] Changer le mot de passe Postgres (rotation effectuée)

### 9. Monitoring
- [ ] Connecter Langfuse (une fois fixé) à Mascarade pour tracer les appels LLM
- [ ] Grafana existant sur la VM — ajouter des dashboards pour les nouveaux services
- [ ] Prometheus — ajouter les endpoints metrics des services

---

## Infra existante sur la VM

| Service | Container | Port |
|---------|-----------|------|
| Ollama | zacus-ollama | 11434 |
| Open WebUI | zacus-open-webui | 3000 |
| Qdrant | zacus-qdrant | 6333 |
| Redis | zacus-redis | 6379 |
| Postgres | zacus-postgres | 5432 |
| Grafana | zacus-grafana | 3001 |
| Prometheus | zacus-prometheus | 9090 |

**Réseau Docker** : `docker-studio-ai_default` (tous les services infra)

## Fichiers clés

```
/mascarade/                  # Repo mascarade (core + api)
/mascarade/.env              # Clés API (à remplir)
/mascarade/docker-compose.yml

~/tools/docker-compose.yml   # Stack outils (Langfuse, n8n, LiteLLM, Dify)
~/tools/litellm-config.yaml  # Config LiteLLM (modèles + cache Redis)
~/tools/clickhouse/config.xml # Config ClickHouse Keeper
~/tools/.env                 # Copie des clés API
```
