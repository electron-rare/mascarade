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
