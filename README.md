# Mascarade

Systeme d'orchestration agentique personnel. Route intelligemment les requetes LLM entre Claude, GPT, Mistral, AWS Bedrock, Google Gemini et Hugging Face, avec agents specialises, orchestration multi-agents, cache, fallback automatique et integration Notion.

## Architecture

```
                         +-----------+
                         |  Client   |
                         | curl/app  |
                         +-----+-----+
                               |
                      :3100    v
                  +--------------------+
                  |   API TypeScript   |
                  |   (Hono + auth)    |
                  +--------+-----------+
                           |
                  :8100    v
          +-------------------------------+
          |        Core Python            |
          |  +--------+  +-----------+    |
          |  | Router |  |  Agents   |    |
          |  | strat. |  | registry  |    |
          |  +---+----+  +-----+-----+    |
          |      |             |          |
          |  +---+---+  +-----+------+   |
          |  | Cache |  |Orchestrator|   |
          |  |Metrics|  | seq/par/   |   |
          |  |Fallbk |  | pipeline   |   |
          |  |  LB   |  +------------+   |
          |  +---+---+                    |
          +------+------------------------+
                 |
    +------------+------------+
    |            |            |
+---v---+  +----v---+  +-----v----+
|Claude |  | OpenAI |  | Mistral  |
+-------+  +--------+  +----------+

                  +--------+
                  | Notion |  (KB + dashboard)
                  +--------+
```

**Core Python** (`core/`, port `8100`) -- Moteur d'orchestration, routeur LLM, agents, metriques
**API TypeScript** (`api/`, port `3100`) -- Facade HTTP Hono, auth middleware, proxy vers le core
**VM** -- Deploiement Docker sur `192.168.0.119`

---

## Prerequis

- **Docker** et **Docker Compose** (deploiement)
- **Python 3.11+** (dev local core)
- **Node.js 22+** (dev local API)
- Au moins une cle API LLM (Anthropic, OpenAI, Mistral, AWS Bedrock ou Google)

Le setup installe aussi un `htop` repo-local epingle en `3.4.0` sous `tools/.local/` et l'expose via `./tools/htop`.
Pourquoi: Ubuntu 24.04 livre `htop 3.3.0`, qui n'inclut pas le meter `GPU usage`. La `3.4.0` ajoute ce meter, utile pour suivre les services GPU du repo sans ecraser le `htop` systeme.

---

## Installation

### 1. Cloner le repo

```bash
git clone <repo-url> mascarade
cd mascarade
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
```

Editer `.env` et remplir les cles :

```bash
# LLM — au moins une cle requise
ANTHROPIC_API_KEY=sk-ant-xxxxx          # Claude (best quality)
OPENAI_API_KEY=sk-xxxxx                 # GPT (fastest)
MISTRAL_API_KEY=xxxxx                   # Mistral (cheapest)
GOOGLE_API_KEY=xxxxx                    # Gemini API (optionnel)
HUGGINGFACE_API_KEY=hf_xxxxx            # Hugging Face Inference
HUGGINGFACE_BASE_URL=https://router.huggingface.co/v1
HUGGINGFACE_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct

# AWS Bedrock (optionnel)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-west-1
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Google Cloud / Vertex (optionnel)
GOOGLE_CLOUD_PROJECT=mon-projet
GOOGLE_CLOUD_LOCATION=europe-west1
GOOGLE_APPLICATION_CREDENTIALS=/chemin/key.json
GOOGLE_MODEL=gemini-2.5-flash

# Notion — optionnel, pour la KB et les dashboards
NOTION_API_KEY=ntn_xxxxx

# Auth — si vide, toutes les routes sont ouvertes (mode dev)
MASCARADE_API_KEY=un-token-secret

# Core
CORE_HOST=0.0.0.0
CORE_PORT=8100

# API
API_PORT=3100
CORE_URL=http://localhost:8100          # http://core:8100 en Docker

# Defauts LLM
DEFAULT_PROVIDER=claude
DEFAULT_MODEL=claude-sonnet-4-6
```

Le routeur active automatiquement les providers dont la cle est presente. Pas de cle = provider ignore.

Validation cloud rapide:

```bash
./scripts/check_aws_bedrock.sh
./scripts/check_google_cloud.sh
```

### 3. Lancer avec Docker (recommande)

```bash
./setup
```

Une fois le setup passe, tu peux lancer le `htop` fourni par le repo avec:

```bash
./tools/htop
```

Si tu veux desactiver ce telechargement repo-local pendant `./setup`, exporte `MASCARADE_SKIP_REPO_HTOP=true`.

Ou en mode non-interactif:

```bash
./setup --with core,api,ops-console --yes
```

Avec `generate-audio` et un vrai smoke test HTTP de `POST /generate`:

```bash
./setup --with core,api,ops-console,generate-audio --smoke-generate-audio --yes
```

`generate-audio` utilise AudioCraft avec une pile PyTorch/XFormers epinglee. En mode `cpu`, le build prend les wheels CPU; en mode `cuda`, le setup bascule vers les wheels CUDA 11.8. Le service emet `gpus: all` et suppose `nvidia-container-toolkit` installe sur l'hote. Les builds CPU et CUDA ont ete verifies localement.

Par defaut, `setup` verifie seulement `GET /health`. Le vrai smoke test `POST /generate` est opt-in avec `--smoke-generate-audio`, car il peut declencher un premier chargement modele plus long.

Deux containers demarrent :
- `core` sur `:8100`
- `api` sur `:3100`
- tous les ports publies utilisent `PUBLISH_BIND_HOST=0.0.0.0` par defaut
- `ops-console` sur `:80` (si selectionne), avec override possible via `OPS_CONSOLE_BIND_HOST`

Si tu veux tout rebloquer en local, remets `PUBLISH_BIND_HOST=127.0.0.1` dans `.env`.
Si tu veux seulement `ops-console` en local, garde `PUBLISH_BIND_HOST=0.0.0.0` et mets `OPS_CONSOLE_BIND_HOST=127.0.0.1`.

Les agents dynamiques sont persistes dans un volume Docker (`core-data:/app/data`).

Verifier que tout tourne :

```bash
# Health du core
curl http://localhost:8100/health

# Health de l'API
curl http://localhost:3100/health

# Health Generate Audio (si selectionne)
curl http://localhost:9000/health

# Smoke test reel Generate Audio (si selectionne)
bash scripts/smoke_generate_audio.sh --url http://localhost:9000
```

### 4. Dev local (sans Docker)

```bash
# Core Python
cd core
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m uvicorn mascarade.server:app --host 0.0.0.0 --port 8100 --reload

# API TypeScript (autre terminal)
cd api
npm install
npm run dev
```

---

## Deploiement sur la VM (192.168.0.119)

### Contexte Docker SSH

Creer un contexte Docker pointe sur la VM :

```bash
docker context create mascarade-vm --docker "host=ssh://user@192.168.0.119"
```

Tester la connexion :

```bash
./scripts/vm-docker.sh ps
```

### Configurer la VM

```bash
cp .env.example .env.vm
```

Editer `.env.vm` :

```bash
VM_HOST=192.168.0.119
VM_API_URL=http://192.168.0.119:3100
VM_CORE_URL=http://192.168.0.119:8100
MASCARADE_API_KEY=ton-token-secret
DOCKER_VM_CONTEXT=mascarade-vm
```

### Deployer / mettre a jour

Le script `deploy/update.sh` gere tout (git pull, tests, build, restart, health check) :

```bash
# Depuis la VM (SSH)
ssh user@192.168.0.119
cd /chemin/vers/mascarade
./deploy/update.sh

# Options
./deploy/update.sh --no-pull          # deployer l'etat local sans git pull
./deploy/update.sh --service core     # rebuild uniquement le core
./deploy/update.sh --service api      # rebuild uniquement l'API
```

### Migration stack IA additionnelle

Pour migrer aussi les services IA lourds (LocalAI, KoboldCPP, AnythingLLM, SGLang, Mem0, Langfuse):

```bash
cd /mascarade
bash scripts/apply_ai_tools_migration.sh /home/cils/tools
```

Puis, au besoin:

```bash
cd /home/cils/tools
docker compose -f docker-compose.yml -f docker-compose.ai.yml --profile heavy up -d localai koboldcpp anythingllm sglang
```

Sur VM legere, garder ces services arretes par defaut (profil `heavy`).

### Interagir avec la VM depuis le Mac

```bash
# Appeler l'API de la VM
./scripts/vm-api.sh /health
./scripts/vm-api.sh /api/agents/providers

# Commandes Docker sur la VM
./scripts/vm-docker.sh logs core --tail=50
./scripts/vm-docker.sh ps
```

---

## Utilisation

### Authentification

Si `MASCARADE_API_KEY` est defini, toutes les routes protegees exigent le header :

```
Authorization: Bearer <MASCARADE_API_KEY>
```

`GET /health` reste toujours public.

Dans les exemples ci-dessous, remplacer `$KEY` par ta cle ou exporter :

```bash
export KEY="ton-token-secret"
```

### Envoyer une requete LLM

```bash
curl -X POST http://localhost:3100/api/agents/send \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Explique le pattern Strategy en 3 lignes"}],
    "strategy": "best"
  }'
```

Strategies disponibles :

| Strategie  | Comportement                                   |
|------------|-------------------------------------------------|
| `best`     | Meilleure qualite (Claude, quality_rank=3)      |
| `cheapest` | Moins cher (Mistral, $2/$6 par M tokens)        |
| `fastest`  | Plus rapide (OpenAI/Mistral, speed_rank=1)      |
| `specific` | Provider specifique (passer `"provider": "..."`) |

### Lister les providers actifs

```bash
curl -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/providers
```

### Agents

9 agents built-in sont charges au demarrage :

| Agent          | Role                                     | Strategie  | Temp |
|----------------|------------------------------------------|------------|------|
| `summarizer`   | Resume en bullet points                  | cheapest   | 0.3  |
| `writer`       | Redaction et reformulation               | best       | 0.8  |
| `coder`        | Code review, debug, generation           | best       | 0.2  |
| `translator`   | Traduction naturelle                     | fastest    | 0.3  |
| `analyst`      | Analyse de donnees et situations         | best       | 0.4  |
| `brainstorm`   | Generation d'idees creatives             | best       | 0.95 |
| `notion-scribe`| Formatage pour Notion                    | cheapest   | 0.4  |
| `planner`      | Planification et decomposition de taches | best       | 0.4  |
| `classifier`   | Classification en JSON (intent, sentiment)| fastest   | 0.1  |

```bash
# Lister les agents
curl -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents

# Executer un agent
curl -X POST http://localhost:3100/api/agents/summarizer/run \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Texte long a resumer..."}]
  }'

# Creer un agent custom (persiste au restart)
curl -X POST http://localhost:3100/api/agents \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mon-agent",
    "description": "Agent custom",
    "system_prompt": "Tu es un expert en ...",
    "strategy": "best",
    "temperature": 0.5
  }'
```

### Orchestration multi-agents

Executer plusieurs agents sur le meme prompt :

```bash
curl -X POST http://localhost:3100/api/agents/orchestrate \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_names": ["analyst", "summarizer"],
    "prompt": "Analyse cette situation : ...",
    "mode": "sequential"
  }'
```

Modes d'execution :

| Mode         | Comportement                                          |
|--------------|-------------------------------------------------------|
| `sequential` | Chaque agent traite le prompt original, un par un     |
| `parallel`   | Tous les agents traitent le prompt en parallele       |
| `pipeline`   | La sortie d'un agent devient l'entree du suivant      |

### Notion

Si `NOTION_API_KEY` est configure :

```bash
# Rechercher dans la KB Notion
curl -H "Authorization: Bearer $KEY" \
  "http://localhost:3100/api/notion/search?q=architecture"

# Lire une page
curl -H "Authorization: Bearer $KEY" \
  http://localhost:3100/api/notion/pages/<page-id>

# Ajouter du contenu a une page
curl -X POST http://localhost:3100/api/notion/pages/<page-id>/append \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "Nouveau contenu a ajouter"}'

# Creer une page
curl -X POST http://localhost:3100/api/notion/pages \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "parent_id": "<parent-page-id>",
    "title": "Ma nouvelle page",
    "content": "Contenu initial"
  }'

# Executer notion-scribe et pousser le resultat dans Notion
curl -X POST http://localhost:3100/api/agents/notion-scribe/run-and-push \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Formate ce rapport : ..."}],
    "push_to": "<page-id>"
  }'
```

### Observabilite

```bash
# Metriques globales (providers + cache + LB + fallback)
curl -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/metrics

# Metriques d'un provider
curl -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/metrics/claude

# Stats cache
curl -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/cache/stats

# Stats load balancer
curl -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/load-balancer/stats

# Stats fallback
curl -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/fallback/stats

# Reset (POST)
curl -X POST -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/metrics/reset
curl -X POST -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/cache/reset
curl -X POST -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/load-balancer/reset
curl -X POST -H "Authorization: Bearer $KEY" http://localhost:3100/api/agents/fallback/reset
```

---

## Providers LLM

| Provider   | Modeles                                          | Cout (in/out par M tokens) | Vitesse | Qualite |
|------------|--------------------------------------------------|---------------------------|---------|---------|
| **Claude** | `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`, `claude-opus-4-6` | $3 / $15 | 2 | 3 (best) |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini`        | $2.50 / $10               | 1 (fast)| 2       |
| **Mistral**| `mistral-large-latest`, `mistral-small-latest`, `codestral-latest` | $2 / $6 | 1 (fast)| 1       |

Resilience integree :
- **Retry** : 3 tentatives avec backoff exponentiel (1s, 2s, 4s) sur rate limit, timeout et erreurs de connexion
- **Fallback** : si le provider choisi echoue, le routeur essaie automatiquement les autres strategies
- **Cache** : reponses identiques servies depuis le cache (TTL 1h)
- **Load Balancer** : distribution round-robin entre providers de meme rang

---

## Tests

```bash
cd core
source .venv/bin/activate
python -m pytest -v       # 42 tests
```

---

## Structure du projet

```
mascarade/
├── core/                             # Python FastAPI
│   ├── mascarade/
│   │   ├── server.py                 # Routes FastAPI + lifespan
│   │   ├── config.py                 # Settings (.env)
│   │   ├── auth.py                   # Bearer token auth
│   │   ├── agents/
│   │   │   ├── base.py               # Dataclass Agent
│   │   │   ├── registry.py           # Registre + persistance JSON
│   │   │   └── skills.py             # 9 agents built-in
│   │   ├── router/
│   │   │   ├── router.py             # Routeur intelligent + cache/metrics/LB/fallback
│   │   │   ├── fallback.py           # Mecanisme de fallback
│   │   │   └── providers/
│   │   │       ├── base.py           # Interface LLMProvider + retry factory
│   │   │       ├── claude.py         # Adapter Anthropic
│   │   │       ├── openai.py         # Adapter OpenAI
│   │   │       └── mistral.py        # Adapter Mistral
│   │   ├── orchestrator/
│   │   │   └── engine.py             # Sequential / parallel / pipeline
│   │   ├── integrations/
│   │   │   └── notion.py             # Client Notion async
│   │   ├── cache/cache.py            # Cache reponses en memoire
│   │   ├── metrics/tracker.py        # Tracking usage/perf
│   │   └── load_balancer/balancer.py # Distribution de charge
│   ├── tests/                        # pytest (42 tests)
│   └── pyproject.toml
├── api/                              # TypeScript Hono
│   ├── src/
│   │   ├── index.ts                  # App Hono + mount routes
│   │   ├── middleware/auth.ts        # Auth middleware Bearer
│   │   ├── client/core.ts            # Client HTTP vers le core
│   │   └── routes/
│   │       ├── health.ts             # GET /health
│   │       ├── agents.ts             # Proxy agents/send/orchestrate
│   │       └── notion.ts             # Proxy Notion
│   └── package.json
├── deploy/
│   ├── Dockerfile.core               # Image Python
│   ├── Dockerfile.api                # Image Node.js
│   └── update.sh                     # Script de deploiement VM
├── scripts/
│   ├── vm-docker.sh                  # Docker via SSH context
│   └── vm-api.sh                     # curl vers l'API de la VM
├── docker-compose.yml
├── .env.example
└── CLAUDE.md                         # Conventions dev
```
