# Mascarade

Système d'orchestration agentique personnel.

## Architecture

- **Core Python** (`core/`) — Moteur d'orchestration, routeur LLM, agents
- **API TypeScript** (`api/`) — Interface HTTP (Hono)
- **Notion** — Base de connaissances + dashboard
- **VM** — Déploiement Docker sur 192.168.0.119

## Quick Start

```bash
# Setup Python core
cd core
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Setup TypeScript API
cd ../api
npm install

# Copy env
cp .env.example .env
# Fill in your API keys

# Run
docker compose up
```

## Providers LLM supportés

- **Claude** (Anthropic) — claude-sonnet-4-6
- **GPT** (OpenAI) — gpt-4o
- **Mistral** — mistral-large-latest

## Stratégies de routage

| Stratégie | Description |
|-----------|-------------|
| `best` | Meilleur modèle disponible (Claude par défaut) |
| `cheapest` | Modèle le moins cher (Mistral) |
| `fastest` | Modèle le plus rapide |
| `specific` | Provider spécifique demandé |

## Endpoints API

### Auth

- Si `MASCARADE_API_KEY` est défini, toutes les routes protégées exigent:
  - `Authorization: Bearer <MASCARADE_API_KEY>`
- Le endpoint `GET /health` reste public.

### Core FastAPI (`core`, port `8100`)

Public:
- `GET /health` — état global

Protégés (auth middleware):
- `POST /send` — envoi LLM avec routing/fallback/cache
- `GET /providers` — providers disponibles
- `GET /agents` / `POST /agents` — lister/créer agents
- `POST /agents/{name}/run` — exécuter un agent
- `POST /orchestrate` — orchestration multi-agents
- `GET /metrics` — résumé métriques (providers + cache + load balancer + fallback)
- `GET /metrics/{provider}` — métriques d’un provider
- `POST /metrics/reset` — reset métriques runtime
- `GET /cache/stats` / `POST /cache/reset` — observabilité cache
- `GET /load-balancer/stats` / `POST /load-balancer/reset` — observabilité load balancing
- `GET /fallback/stats` / `POST /fallback/reset` — observabilité fallback

### API Hono (`api`, port `3000`)

- `GET /health` — health de la façade + état du core
- `POST /api/agents/send` — proxy vers core `/send`
- `GET /api/agents/providers` — proxy vers core `/providers`
- `GET /api/agents/metrics` — proxy vers core `/metrics`
- `GET /api/agents/metrics/:provider` — proxy vers core `/metrics/{provider}`
- `POST /api/agents/metrics/reset` — proxy reset métriques
- `GET /api/agents/cache/stats` / `POST /api/agents/cache/reset`
- `GET /api/agents/load-balancer/stats` / `POST /api/agents/load-balancer/reset`
- `GET /api/agents/fallback/stats` / `POST /api/agents/fallback/reset`

### Exemples `curl`

```bash
# Résumé des métriques
curl -H "Authorization: Bearer $MASCARADE_API_KEY" \
  http://localhost:3000/api/agents/metrics

# Stats cache
curl -H "Authorization: Bearer $MASCARADE_API_KEY" \
  http://localhost:3000/api/agents/cache/stats

# Reset fallback
curl -X POST -H "Authorization: Bearer $MASCARADE_API_KEY" \
  http://localhost:3000/api/agents/fallback/reset
```
