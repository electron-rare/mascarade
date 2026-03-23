# VS Code Assistants

## Objectif

Reprendre deux usages concrets dans VS Code :

1. un assistant de coding piloté par les CLI externes (`vibe`, `codex`, `claude-code`) ;
2. un assistant Mascarade appelable depuis l'éditeur sans passer directement par le core Python.

## Ce qui est disponible

- API gateway : `http://localhost:3000`
- Core Python : `http://localhost:8100`
- Route CLI agents côté API : `GET /api/cli-agents/status`, `POST /api/cli-agents/run`
- Route OpenAI-compatible côté API : `POST /api/v1/chat/completions`

## Pourquoi passer par `/api/cli-agents`

Le core sait déjà lancer `vibe`, `codex` et `claude-code`, mais l'usage VS Code est plus simple si l'éditeur parle à l'API gateway Node :

- auth et rate-limit homogènes ;
- URL unique pour les clients locaux ;
- pas besoin d'exposer directement le core à l'éditeur.

## Pré-requis

- API Mascarade lancée sur `:3000`
- Core Mascarade lancé sur `:8100`
- binaire CLI installé pour l'agent visé :
  - `vibe`
  - `codex`
  - `claude`

## Vérification rapide

```bash
curl -s http://localhost:3000/api/cli-agents/status \
  -H "Authorization: Bearer $MASCARADE_API_KEY"
```

```bash
curl -s http://localhost:3000/api/cli-agents/run \
  -H "Authorization: Bearer $MASCARADE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "vibe",
    "prompt": "Analyse ce dépôt et propose le plus petit correctif sûr.",
    "workdir": "/Users/electron/Documents/Projets/mascarade",
    "max_turns": 3
  }'
```

## Usage dans VS Code

Le plus simple est d'utiliser un fichier `.http` dans VS Code via REST Client ou un équivalent. Un exemple prêt à l'emploi est disponible ici :

- `docs/examples/vscode/cli-agents.http`

Ce flux est pratique pour :

- tester `vibe` sans écrire de code d'intégration ;
- comparer `vibe`, `codex` et `claude-code` sur le même prompt ;
- garder une trace des prompts de debug dans le repo.

## Cline et Cody

Pour brancher un assistant VS Code sans développer une extension maison, le chemin le plus propre dans ce repo est maintenant le MCP stdio local de Mascarade.

- launcher commun : `scripts/vscode/mascarade_mcp_stdio.js`
- serveur MCP : `python -m mascarade.mcp.server`
- tools exposés : `list_agents`, `run_agent`, `search_knowledge_base`, `list_providers`, `orchestrate`

Guide dédié :

- `docs/VSCODE_CLINE_CODY_MCP_2026-03-22.md`

## Note sur l'assistant “chat” dans VS Code

Mascarade expose aussi `POST /api/v1/chat/completions`.

- si `project_id` est omis, la gateway injecte `MASCARADE_PROJECT_ID`, ou `default` si la variable n'est pas définie ;
- `knowledge_scope` reste par défaut à `project` ;
- pour un assistant VS Code en mode OpenAI-compatible, c'est donc maintenant le chemin le plus direct.

`/api/cli-agents/run` reste utile quand on veut piloter explicitement `vibe`, `codex` ou `claude-code` comme agents CLI plutôt qu'un backend chat compatible OpenAI.
