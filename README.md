# Mascarade

Systeme d'orchestration agentique personnel. Route intelligemment les requetes LLM entre Claude, GPT, Mistral, AWS Bedrock, Google Gemini et Hugging Face, avec agents specialises, orchestration multi-agents, cache, fallback automatique et surfaces runtime `knowledge-base` / `cad`.

## Ecosysteme

Mascarade fait partie d'un ecosysteme de 5 repos :

| Repo | Role |
|------|------|
| **[mascarade](https://github.com/electron-rare/mascarade)** | Repo compagnon runtime/ops, orchestration agentique, fine-tuning et bridge historique |
| **[mascarade-datasets](https://github.com/electron-rare/mascarade-datasets)** | Datasets de fine-tuning (13 domaines, ~74k exemples) |
| **[mascarade-cockpit](https://github.com/electron-rare/mascarade-cockpit)** | Console ops SvelteKit (monitoring Docker, metriques, energie) |
| **[crazy_life](https://github.com/electron-rare/crazy_life)** | Repo canonique web/devops du cockpit et de la surface `Crazy Lane` |
| **[Kill_LIFE](https://github.com/electron-rare/Kill_LIFE)** | Template agentique pour projets embarques IA (spec-first, gates, evidence packs) |

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

                  +------------------+
                  | Knowledge Base / |
                  | MCP integrations |
                  +------------------+
```

## API Versioning & Stability Contract

Mascarade formalise son contrat de stabilite API avec un versioning explicite. Contrairement a LiteLLM (releases multiples par jour avec breaking changes) ou LangChain (0.1→0.2→0.3 avec cassures), Mascarade garantit la stabilite de son API pour les operateurs qui privilegient la fiabilite sur les features bleeding-edge.

### Version Actuelle : API v1.0.0

Tous les endpoints sont prefixes par `/v1/` (Python core) ou `/v1/api/` (TypeScript API).

**Endpoints de version :**
- `GET /v1/version` (Python core, port 8100) — version API, features supportees, liste providers
- `GET /v1/version` (TypeScript API, port 3100) — version API aggregee depuis le core

**Exemples :**
```bash
# Python Core API (port 8100)
curl http://localhost:8100/v1/version
curl -X POST http://localhost:8100/v1/agents/send -H "Authorization: Bearer $MASCARADE_API_KEY" -d '...'
curl -X POST http://localhost:8100/v1/chat/completions -H "Authorization: Bearer $MASCARADE_API_KEY" -d '...'

# TypeScript API Gateway (port 3100)
curl http://localhost:3100/v1/version
curl http://localhost:3100/v1/api/agents/list -H "Authorization: Bearer $MASCARADE_API_KEY"
```

### Contrats Geles (Frozen Contracts)

Les endpoints suivants ont un contrat gele et **ne changeront pas** en v1.x :

**`POST /v1/chat/completions`** — Interface OpenAI-compatible
- Schema request/response identique a OpenAI API v1
- Parametres supportes : `messages`, `model`, `temperature`, `max_tokens`, `stream`
- Reponse inclut : `id`, `object`, `created`, `choices`, `usage`
- **Tout changement a ce contrat est considere BREAKING**

### Garanties de Stabilite

#### Backward Compatibility Promise

**Aucun breaking change** ne sera introduit dans les releases v1.x :
- De nouveaux champs peuvent etre ajoutes aux reponses (clients doivent ignorer les champs inconnus)
- De nouveaux parametres optionnels peuvent etre ajoutes
- Les features deprecies seront supportees pendant **minimum 6 mois** avec warnings
- Un guide de migration sera fourni avant tout changement breaking v2.0

#### Politique de Deprecation

Les endpoints deprecies retournent les headers HTTP suivants (RFC 8594) :
- `Deprecation: true` — endpoint marque comme deprecie
- `Warning: "299 - This endpoint will be removed in API v2.0"` — message d'avertissement
- `Sunset: 2026-09-15T00:00:00Z` — date de retrait prevue
- `Link: </v2/new-endpoint>; rel="alternate"` — endpoint de remplacement
- `X-Deprecated-Since: 1.5.0` — version de deprecation

Support minimum : **6 mois** entre deprecation et retrait effectif.

### Classification des Changements

| Label | Signification | Action Requise |
|-------|---------------|----------------|
| **[BREAKING]** | Change le contrat existant | Mise a jour client obligatoire |
| **[DEPRECATED]** | Sera retire dans une version future | Planifier migration |
| **[ADDED]** | Nouvelle feature ou endpoint | Aucune (opt-in) |
| **[CHANGED]** | Modification non-breaking | Aucune |
| **[FIXED]** | Correction de bug | Aucune |
| **[SECURITY]** | Changement lie a la securite | Review recommande |

### Breaking Changes = Nouvelle Version API

Un breaking change declenche un nouveau prefix de version (`/v2/`) avec periode de migration :
- La v1 continue de fonctionner pendant la periode de migration (minimum 6 mois)
- Un guide de migration detaille est fourni
- Les deux versions coexistent jusqu'au sunset de la v1

**Exemple de migration future v1 → v2 :**
```bash
# v1 (deprecated mais encore supportee)
POST /v1/agents/send

# v2 (nouveau contrat)
POST /v2/agents/execute
```

### Tests de Regression

Le contrat API est protege par **45+ tests de regression** :
- `core/tests/test_api_versioning.py` — tests de versioning (11 tests)
- `core/tests/test_openai_compat.py` — contrat OpenAI gele (7 tests de stabilite)
- `api/src/routes/*.test.ts` — tests TypeScript API (34 tests)

**Execution :**
```bash
# Tests Python
cd core && python -m pytest tests/test_api_versioning.py -v
cd core && python -m pytest tests/test_openai_compat.py -v

# Tests TypeScript
cd api && npm test
```

### Changelog

Tous les changements API sont documentes dans [`CHANGELOG.md`](./CHANGELOG.md) avec labels breaking/non-breaking.

**Consulter le changelog :**
```bash
cat CHANGELOG.md
```

### Access Programmatique a la Version

**Python :**
```python
from mascarade.api_version import API_VERSION, get_version_info

print(API_VERSION)  # "1.0.0"

info = get_version_info()
print(info["stability_level"])  # "stable"
print(info["frozen_contracts"])  # ["/v1/chat/completions"]
```

**TypeScript / JavaScript :**
```typescript
const response = await fetch('http://localhost:3100/v1/version');
const version = await response.json();

console.log(version.api_version);  // "0.1.0"
console.log(version.core_version);  # "1.0.0"
console.log(version.supported_features);  // ["agents", "router", "cache", ...]
```

## Suivi
- backlog ANE dedie: [`TODO_AI_NOVEL_ENGINE.md`](./TODO_AI_NOVEL_ENGINE.md)
- plan d'execution global: [`docs/EXECUTION_PLAN_2026-03-08.md`](./docs/EXECUTION_PLAN_2026-03-08.md)
- runbook Apple local: [`docs/RUNBOOK_APPLE_LLM_LOCAL.md`](./docs/RUNBOOK_APPLE_LLM_LOCAL.md)
- l'integration `ai-novel-engine` reste limitee au runtime local et au contrat OpenAI-compatible

**Core Python** (`core/`, port `8100`) -- Moteur d'orchestration, routeur LLM, agents, metriques
**API TypeScript** (`api/`, port `3100`) -- Facade HTTP Hono, auth middleware, proxy vers le core
**VM** -- Deploiement Docker sur `192.168.0.119`

---

## Crazy Life (frontend)

`mascarade` pilote l'operateur local et le runtime Docker de cette machine.
`mascarade/web/` est un subtree bridge vers le repo canonique [crazy_life](https://github.com/electron-rare/crazy_life).

Contrat courant:
- `crazy_life` = repo canonique web/devops et release du shell cockpit
- `Kill_LIFE` = source de verite runtime, workflows JSON, evidence, firmware, CAD et compliance
- `mascarade` = repo compagnon/orchestration + bridge historique optionnel

```bash
scripts/sync_crazy_life.sh status          # Etat de sync
scripts/sync_crazy_life.sh push            # export bridge web/ -> crazy_life
scripts/sync_crazy_life.sh pull            # crazy_life/main -> web/
npm --prefix web run build                 # build local dans web/dist
npm --prefix web run build:api-public      # refresh explicite du snapshot api/public
```

Rappel operatoire:
- `scripts/sync_crazy_life.sh` ne publie pas une release canonique
- la readiness de release vit dans `crazy_life`, via `scripts/publish_preflight.sh`

### Boucle "next useful lot"

Les scripts canoniques pour enchainer automatiquement sur le prochain lot utile
local sont:

```bash
bash scripts/next_useful_lot.sh detect
bash scripts/next_useful_lot.sh checks
bash scripts/run_next_useful_lot.sh
```

Contrat:
- `detect` choisit le lot local le plus utile encore ouvert
- `checks` rejoue ses validations canoniques
- `run_next_useful_lot.sh` fait `detect + checks + refresh` de
  `docs/NEXT_USEFUL_LOT_STATE.md`

Le fichier versionne [NEXT_USEFUL_LOT_STATE.md](/home/clems/mascarade/docs/NEXT_USEFUL_LOT_STATE.md)
devient la note de handoff court terme pour le lot actif.

---

## Fine-Tuning

Pipeline de fine-tuning QLoRA pour modeles code specialises electronique embarquee.

- **Profil operateur** : derive du materiel detecte
- **Machine validee ici** : RTX 4090 24 Go
- **Student auto courant** : `Qwen/Qwen3.5-9B-Base`
- **10 domaines** : stm32, spice, iot, power, dsp, emc, kicad, embedded, platformio, freecad
- **Datasets** : ~74k exemples au format ShareGPT (repo [mascarade-datasets](https://github.com/electron-rare/mascarade-datasets))
- **Racine canonique des modeles** : `/ai/llm`

Runbook detaille:

- [docs/FINETUNING_OPERATOR_RUNBOOK.md](/ai/saisail/mascarade/docs/FINETUNING_OPERATOR_RUNBOOK.md)

```bash
cd /ai/saisail/mascarade
. ./scripts/llm_env.sh

# Selection/veille du student
venv_tuning/bin/python finetune/model_selector.py --watch --refresh --task code --top 6 --auto

# Entrainement local auto
venv_tuning/bin/python finetune/run_local.py stm32

# Prochain lot utile
./scripts/next_finetune_lots.sh --skip-cad-smoke --skip-components-review
./scripts/bench_watch_candidate.sh
./scripts/bench_watch_candidate.sh --execute
./scripts/auto_chain_next_lots_loop.sh --iterations 1 --sleep-seconds 600 --max-blocked-streak 12 --max-cycles 0

# Consolidation des caches/modeles
./scripts/migrate_models_to_llm.sh
./scripts/migrate_models_to_llm.sh --execute --cleanup --link-home-cache
```

---

## Prerequis

- **Docker** et **Docker Compose** (deploiement)
- **Python 3.11+** (dev local core)
- **Node.js 22+** (dev local API)
- `MASCARADE_API_KEY` pour un runtime protege
- Au moins un provider LLM configure, ou `OLLAMA_ENABLED=true` avec un runtime Ollama joignable

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

- `required-security`: `MASCARADE_API_KEY` protege l'API, le core et l'ops-agent.
- `feature-required`: providers LLM et integrations que vous activez reellement.
- `live-validation-optional`: cibles de smoke/runtime live seulement.
- `local-operator-context`: endpoints OAuth, chemins et overrides locaux.

```bash
# Runtime security — toujours requis pour un runtime protege
MASCARADE_API_KEY=un-token-secret

# Providers LLM — configurer seulement ce que vous utilisez
ANTHROPIC_API_KEY=sk-ant-xxxxx          # Claude (best quality)
OPENAI_API_KEY=sk-xxxxx                 # GPT (fastest)
MISTRAL_API_KEY=xxxxx                   # Mistral (cheapest)
GOOGLE_API_KEY=xxxxx                    # Gemini API (mode api_key)
GOOGLE_AUTH_MODE=api_key                # or oauth_oidc or adc
GOOGLE_OAUTH_ACCESS_TOKEN=
GOOGLE_OAUTH_REFRESH_TOKEN=
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_TOKEN_ENDPOINT=https://oauth2.googleapis.com/token
GOOGLE_OAUTH_EXPIRES_AT=
HUGGINGFACE_API_KEY=hf_xxxxx            # Hugging Face Inference (mode api_key)
HUGGINGFACE_AUTH_MODE=api_key           # or oauth_oidc
HUGGINGFACE_BASE_URL=https://router.huggingface.co/v1
HUGGINGFACE_OAUTH_ACCESS_TOKEN=
HUGGINGFACE_OAUTH_REFRESH_TOKEN=
HUGGINGFACE_OAUTH_CLIENT_ID=
HUGGINGFACE_OAUTH_CLIENT_SECRET=
HUGGINGFACE_OAUTH_TOKEN_ENDPOINT=https://huggingface.co/oauth/token
HUGGINGFACE_OAUTH_EXPIRES_AT=
HUGGINGFACE_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct

# AWS Bedrock (optionnel)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-west-1
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Google Cloud / Vertex (optionnel, requis en mode adc et utilisable aussi avec oauth_oidc)
GOOGLE_CLOUD_PROJECT=mon-projet
GOOGLE_CLOUD_LOCATION=europe-west1
GOOGLE_APPLICATION_CREDENTIALS=/chemin/key.json
GOOGLE_MODEL=gemini-2.5-flash

# GitHub dispatch — integration optionnelle
GITHUB_DISPATCH_AUTH_MODE=token       # or app
KILL_LIFE_GITHUB_TOKEN=ghp_xxxxx
GITHUB_TOKEN=
GITHUB_APP_ID=
GITHUB_APP_PRIVATE_KEY=
GITHUB_APP_INSTALLATION_ID=

# Firecrawl MCP — integration optionnelle
FIRECRAWL_HOST=0.0.0.0
FIRECRAWL_API_KEY=fc_xxxxx
FIRECRAWL_API_URL=                     # optionnel, seulement si vous ciblez une API Firecrawl self-hosted

# Mem0 / OpenMemory — integration optionnelle
MEM0_USER=mascarade
MEM0_OPENAI_API_KEY=sk-mem0-local    # si LiteLLM a une master key, reprendre la meme ici
MEM0_OPENAI_BASE_URL=http://litellm:4000
MEM0_QDRANT_HOST=qdrant
MEM0_QDRANT_PORT=6333

# Core
CORE_HOST=0.0.0.0
CORE_PORT=8100

# API
API_PORT=3100
CORE_URL=http://localhost:8100          # http://core:8100 en Docker

# Ollama (Docker ou hote natif)
OLLAMA_ENABLED=true
OLLAMA_HOST_MODE=docker
OLLAMA_BASE_URL=http://ollama:11434    # macOS natif: http://host.docker.internal:11434
OLLAMA_TIMEOUT_SECONDS=180             # augmenter pour les smokes ANE longs

# Apple LLM natif (service hote macOS pour Core ML / ANE)
APPLE_LLM_ENABLED=false
APPLE_LLM_BASE_URL=http://host.docker.internal:8201  # dev local hors Docker: http://127.0.0.1:8201
APPLE_LLM_MODEL_ID=apple-local
APPLE_LLM_BACKEND=coreml                              # ou onnx-coreml
APPLE_LLM_MODEL_PATH=/chemin/model.mlpackage          # onnx-coreml: /chemin/model.onnx
APPLE_LLM_EMBED_MODEL_PATH=/chemin/embed_tokens.mlpackage  # optionnel, requis si le modele attend inputs_embeds
APPLE_LLM_TOKENIZER_PATH=/chemin/tokenizer
APPLE_LLM_COMPUTE_UNITS=cpu_and_ne
APPLE_LLM_ENABLE_THINKING=false                      # Qwen3.5: false pour une reponse directe

# Defauts LLM
DEFAULT_PROVIDER=claude
DEFAULT_MODEL=claude-sonnet-4-6
```

Le routeur active automatiquement les providers dont la cle est presente. Pas de cle = provider ignore.

Note:
- `Notion` n'est plus dans le scope operateur actif de `mascarade`.
- Les variables `NOTION_*` ne doivent plus etre traitees comme prerequis courants.
- Les chemins `Notion` encore presents dans le repo relevent de la compatibilite legacy uniquement.

## CAD / EDA

Une stack Docker dédiée `KiCad headless`, `KiCad MCP`, `FreeCAD` et `PlatformIO` est disponible dans [deploy/cad/README.md](/home/clems/mascarade/deploy/cad/README.md).

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
./setup --with core,api,ops-console,ollama --yes
```

Sur macOS Apple Silicon (M1 a M5), le profil dedie privilegie une stack legere. Si Ollama natif est installe, `setup` configure automatiquement `OLLAMA_BASE_URL` pour que les conteneurs parlent a l'hote:

```bash
MASCARADE_TUI_MODE=plain ./setup --profile apple-silicon --yes
```

Ce profil est pense pour les outils locaux Apple Silicon actuels:

- Ollama natif pour le serving local simple
- MLX / `mlx-lm` pour l'experimentation Apple Silicon
- Core ML / ONNX Runtime CoreML EP pour un vrai chemin Neural Engine

Pour brancher un vrai service local Apple Silicon / Neural Engine, Mascarade expose maintenant un provider `apple-coreml` qui parle a un service hote macOS:

```bash
./scripts/install_apple_coreml_model.sh

export APPLE_LLM_ENABLED=true
export APPLE_LLM_BASE_URL=http://host.docker.internal:8201
export APPLE_LLM_MODEL_ID=stateful-mistral7b-instruct-int4-coreml
export APPLE_LLM_BACKEND=coreml
export APPLE_LLM_TIMEOUT_SECONDS=900
export APPLE_LLM_MODEL_PATH="$HOME/Models/mascarade/apple-llm/StatefulMistral7BInstructInt4/StatefulMistral7BInstructInt4.mlpackage"
export APPLE_LLM_TOKENIZER_PATH="$HOME/Models/mascarade/apple-llm/StatefulMistral7BInstructInt4/tokenizer"

./scripts/run_apple_llm_service.sh
```

Pour les smokes `ai-novel-engine`, prevoir un timeout Apple plus large que les providers cloud: le warm-up Core ML peut depasser plusieurs minutes sur le premier appel.

Validation locale utile pour `ai-novel-engine` au 8 mars 2026:
- sous protocole ANE avec garde-fou actif, aucun modele n'est encore `accepted`
- sous protocole ANE avec boucle `repair`, aucun modele n'atteint encore `gate` en live
- `apple-coreml:qwen2.5-0.5b-instruct-onnx` atteint `rewrite` puis timeoute a `300s`
- `apple-coreml:qwen3.5-4b-onnx-q4f16` atteint `rewrite` avec une critique exploitable puis timeoute a `300s`
- `ollama:qwen2.5:1.5b` timeoute en `structure` via le service Docker CPU
- `ollama:qwen2.5:7b` atteint `rewrite` avec une critique exploitable puis timeoute a `300s`
- `apple-coreml:stateful-mistral7b-instruct-int4-coreml` repond au preflight, mais reste preflight-only pour ANE sur cette machine
- pour les smokes ANE qualitatifs sur le service Docker CPU, prevoir un `OLLAMA_TIMEOUT_SECONDS` plus large que `180` si les requetes de structure ou de draft depassent plusieurs minutes
- le runtime Apple local ne sert qu'un seul `model_id` a la fois; pour comparer plusieurs modeles Apple, il faut relancer `:8201` entre deux runs

Si tu as deja un export Core ML natif produit ailleurs, tu peux aussi le stage dans un layout stable pour Mascarade:

```bash
./scripts/stage_apple_coreml_model.sh \
  --model-source ~/Exports/Qwen3.5/decoder_model_merged.mlpackage \
  --embed-source ~/Exports/Qwen3.5/embed_tokens.mlpackage \
  --tokenizer-source ~/Exports/Qwen3.5/tokenizer \
  --dest ~/Models/mascarade/apple-llm/Qwen3.5-4B-CoreML \
  --model-id qwen3.5-4b-coreml

export APPLE_LLM_ENABLED=true
export APPLE_LLM_BASE_URL=http://host.docker.internal:8201
export APPLE_LLM_MODEL_ID=qwen3.5-4b-coreml
export APPLE_LLM_BACKEND=coreml
export APPLE_LLM_MODEL_PATH="$HOME/Models/mascarade/apple-llm/Qwen3.5-4B-CoreML/decoder_model_merged.mlpackage"
export APPLE_LLM_EMBED_MODEL_PATH="$HOME/Models/mascarade/apple-llm/Qwen3.5-4B-CoreML/embed_tokens.mlpackage"
export APPLE_LLM_TOKENIZER_PATH="$HOME/Models/mascarade/apple-llm/Qwen3.5-4B-CoreML/tokenizer"
export APPLE_LLM_ENABLE_THINKING=false

./scripts/run_apple_llm_service.sh
./scripts/smoke_apple_llm.sh --url http://127.0.0.1:8201 --model qwen3.5-4b-coreml
```

Le chemin ONNX reste disponible comme fallback de compatibilite:

```bash
./scripts/install_apple_llm_model.sh

export APPLE_LLM_ENABLED=true
export APPLE_LLM_BASE_URL=http://host.docker.internal:8201
export APPLE_LLM_MODEL_ID=qwen3.5-4b-onnx-q4f16
export APPLE_LLM_BACKEND=onnx-coreml
export APPLE_LLM_MODEL_PATH="/ai/llm/apple-llm/Qwen3.5-4B-ONNX-q4f16/onnx/decoder_model_merged_q4f16.onnx"
export APPLE_LLM_TOKENIZER_PATH="/ai/llm/apple-llm/Qwen3.5-4B-ONNX-q4f16"
export APPLE_LLM_ENABLE_THINKING=false

./scripts/run_apple_llm_service.sh
./scripts/smoke_apple_llm.sh --url http://127.0.0.1:8201 --model qwen3.5-4b-onnx-q4f16
```

Ensuite, pour que le routeur utilise ce chemin:

```bash
DEFAULT_PROVIDER=apple-coreml
DEFAULT_MODEL=<meme-valeur-que-APPLE_LLM_MODEL_ID>
```

Notes:

- `scripts/stage_apple_coreml_model.sh` stage un export Core ML natif dans un layout stable pour `APPLE_LLM_BACKEND=coreml`
- `scripts/install_apple_coreml_model.sh` telecharge un artefact Core ML natif depuis Hugging Face avec son tokenizer associe
- `scripts/install_apple_llm_model.sh` installe par defaut `onnx-community/Qwen3.5-4B-ONNX` avec `onnx/decoder_model_merged_q4f16.onnx` et `onnx/embed_tokens_q4f16.onnx`
- `APPLE_LLM_BACKEND=coreml` attend un modele Core ML exporte, typiquement `.mlpackage` ou `.mlmodelc`
- `APPLE_LLM_EMBED_MODEL_PATH` est optionnel, mais devient utile des qu'un export natif attend `inputs_embeds`
- `scripts/run_apple_llm_service.sh` prefere automatiquement `python3.12` pour `coreml`; si seule une venv `Python 3.14` existe, `coremltools` ne charge pas le runtime natif attendu
- `APPLE_LLM_BACKEND=onnx-coreml` attend un modele `.onnx` execute via ONNX Runtime CoreML EP
- ce service est volontairement hote natif macOS; Docker Desktop n'expose pas le Neural Engine au conteneur
- le moteur implemente un chemin autoregressif simple, utile pour prototyper et valider le routage Mascarade vers un runtime ANE
- le chemin `coreml` charge maintenant un vrai artefact natif, expose ses specs d'entree dans `/health`, et supporte aussi les modèles Core ML stateful
- le chemin Qwen3.5 utilise un export ONNX moderne avec `inputs_embeds`, `embed_tokens` et cache mixte `past_key_values` / `past_conv` / `past_recurrent`
- `APPLE_LLM_ENABLE_THINKING=false` desactive le mode thinking de `Qwen3.5` via son chat template officiel
- `Qwen2.5-0.5B-Instruct` reste un fallback valide sur cette machine si un graphe plus simple est prefere

Avec `generate-audio` et un vrai smoke test HTTP de `POST /generate`:

```bash
./setup --with core,api,ops-console,generate-audio,ollama --smoke-generate-audio --yes
```

`generate-audio` utilise AudioCraft avec une pile PyTorch/XFormers epinglee. En mode `cpu`, le build prend les wheels CPU; en mode `cuda`, le setup bascule vers les wheels CUDA 11.8. Le service emet `gpus: all` et suppose `nvidia-container-toolkit` installe sur l'hote. Les builds CPU et CUDA ont ete verifies localement.

Par defaut, `generate-audio` charge maintenant le modele seulement au moment de `POST /generate`, puis le decharge apres la requete. Il n'est donc plus cense garder plusieurs Go de VRAM en resident entre deux usages. Tu peux changer ce comportement avec:

```bash
GENERATE_AUDIO_KEEP_LOADED=true
GENERATE_AUDIO_IDLE_UNLOAD_SECONDS=300
```

et le liberer explicitement avec:

```bash
curl -X POST http://localhost:9000/unload
```

Par defaut, `setup` verifie seulement `GET /health`. Le vrai smoke test `POST /generate` est opt-in avec `--smoke-generate-audio`, car il peut declencher un premier chargement modele plus long.

Si la machine a deja un service Ollama systeme avec ses modeles sous `/usr/share/ollama/.ollama`, la stack peut reutiliser ce stockage via:

```bash
OLLAMA_PUBLISH_PORT=false
OLLAMA_HOST_MODELS_DIR=/usr/share/ollama/.ollama
```

Dans ce mode, `ollama` reste interne au reseau Docker de Mascarade et n'entre pas en conflit avec un `127.0.0.1:11434` deja occupe sur l'hote.

Le `setup` prend maintenant cette variante comme default quand il detecte deja un `11434` occupe et un store Ollama local present.

Pour les ecarts de portabilite machine/VM, les garde-fous Docker/GPU et les
limites observees pendant le portage, voir `docs/PORTAGE_MASCARADE.md`.

Deux containers demarrent :
- `core` sur `:8100`
- `api` sur `:3100`
- le cockpit expose maintenant une vraie lane `Logs` sur `http://localhost:3100/logs`
- tous les ports publies utilisent maintenant `PUBLISH_BIND_HOST=127.0.0.1` par defaut
- `ops-console` sur `:80` (si selectionne), avec override possible via `OPS_CONSOLE_BIND_HOST`
- `edge-proxy` peut exposer seulement `:80/:443` pour l'entree publique

Si tu veux tout garder en local, laisse `PUBLISH_BIND_HOST=127.0.0.1` dans `.env`.
Si tu veux exposer des services internes au LAN, passe explicitement `PUBLISH_BIND_HOST=0.0.0.0`.
Si tu veux publier `edge-proxy` sur `:80/:443`, passe explicitement `EDGE_PROXY_BIND_HOST=0.0.0.0`.

Mode reverse proxy:

```bash
PUBLISH_BIND_HOST=127.0.0.1 ./setup --with core,api,ops-console,edge-proxy --yes
```

Dans ce mode, seuls `edge-proxy` sur `:80/:443` sont publics si `EDGE_PROXY_BIND_HOST=0.0.0.0`; sinon toute la stack reste sur loopback.

Observability complementaire opt-in:

```bash
./setup --with core,api,ops-console,loki,promtail,otel-collector --yes
```

Ce lot ajoute le stockage/relais observability, mais le cockpit utilise deja aujourd'hui la trace native du core pour afficher les echanges inter-agent dans `Logs`.
Pour la pile observability complete, ajouter aussi `prometheus,grafana,tempo,blackbox-exporter,langfuse`.

`Tempo` est maintenant le backend de traces nominal pour Grafana. `Loki` reste la source de logs et `Prometheus` la source de metriques; `blackbox-exporter` complete la couverture des services qui n'exposent pas `/metrics`.

Surfaces operateur proxifiees:

```bash
EDGE_PROXY_GRAFANA_SERVER_NAME=grafana.saillant.cc
EDGE_PROXY_LANGFUSE_SERVER_NAME=langfuse.saillant.cc
GRAFANA_PUBLIC_ORIGIN=https://grafana.saillant.cc
LANGFUSE_PUBLIC_ORIGIN=https://langfuse.saillant.cc
EDGE_PROXY_OPS_AUTH_USER=ops
EDGE_PROXY_OPS_AUTH_PASSWORD=...
```

Avec ces variables, `Grafana` et `Langfuse` passent derriere `edge-proxy` avec une auth dediee au proxy. Par defaut, ce routage reste seulement sur loopback tant que `EDGE_PROXY_BIND_HOST=127.0.0.1`.

Smoke test OTLP -> Loki:

```bash
bash scripts/smoke_otel_loki.sh
bash scripts/smoke_otel_loki.sh --json
```

Report de cardinalite Loki:

```bash
bash scripts/loki_cardinality_report.sh
bash scripts/loki_cardinality_report.sh --json
```

Certificat Let's Encrypt par DNS-01 Cloudflare:

```bash
# Variables minimales dans .env
EDGE_PROXY_SERVER_NAME=saillant.cc
EDGE_PROXY_ACME_EMAIL=toi@example.com
EDGE_PROXY_ACME_DOMAINS=saillant.cc,grafana.saillant.cc,langfuse.saillant.cc,dify.saillant.cc
CLOUDFLARE_API_TOKEN=...              # API token Cloudflare
# ou, si tu utilises une Global API Key:
CLOUDFLARE_API_EMAIL=toi@example.com
CLOUDFLARE_API_KEY=...

# Emission du certificat
bash scripts/edge_proxy_cert.sh issue
```

Le proxy continue a generer un certificat auto-signe tant qu'aucun certificat reel n'est installe. Une fois le certificat emis, `edge-proxy` recharge Nginx automatiquement.

Sur la machine de reference, le certificat reel en place couvre maintenant
`saillant.cc` et `*.saillant.cc`, ce qui absorbe `grafana.saillant.cc`,
`langfuse.saillant.cc` et `dify.saillant.cc`.

Si tu restes en provider `manual`, le flux devient:

```bash
bash scripts/edge_proxy_cert.sh issue --provider manual
# ajouter les TXT ACME demandes par le script
bash scripts/edge_proxy_cert.sh renew --provider manual
```

Sur la machine de reference, `edge-proxy` est maintenant publie sur `0.0.0.0:80/443`, avec les hostnames `saillant.cc`, `grafana.saillant.cc`, `langfuse.saillant.cc` et `dify.saillant.cc`.

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
bash scripts/bootstrap_python_env.sh
cd core
source .venv/bin/activate
python -m uvicorn mascarade.server:app --host 0.0.0.0 --port 8100 --reload

# API TypeScript (autre terminal)
cd api
npm install
npm run dev
```

Validation repo-locale recommandee avant tout tri de delta:

```bash
bash scripts/test_python.sh
curl -fsS http://127.0.0.1:8100/health
curl -fsS http://127.0.0.1:3100/health
curl -fsS http://127.0.0.1:9200/health
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

`Langfuse` reste une brique supportee du repo, mais optionnelle hors profil standard. `Firecrawl` est supporte comme service MCP optionnel via l'image officielle `mcp/firecrawl`; il exige `FIRECRAWL_API_KEY` ou `FIRECRAWL_API_URL` pour demarrer. `Mem0` est supporte via `mem0/openmemory-mcp`, adosse a `Qdrant` et route par defaut ses appels OpenAI-compatibles vers `LiteLLM`.
`Tempo` est supporte comme backend traces de reference de la stack observability locale, et les surfaces operateur `Grafana` / `Langfuse` peuvent etre publiees derriere `edge-proxy` sans exposer `Prometheus` ni les services internes.

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

### Utiliser l'endpoint OpenAI-compatible

Le core Python expose aussi un shim local `POST /v1/chat/completions` sur `:8100`.
Il est utile pour brancher des outils qui parlent deja l'API OpenAI, sans leur
ajouter de logique provider Mascarade.

Selection du backend local par `model` :

- `apple-coreml:<model-id>`
- `ollama:<model-id>`
- sans prefixe, Mascarade retombe sur `DEFAULT_PROVIDER` et `DEFAULT_MODEL`

Le modele doit rester explicite dans les smokes ANE. Les exemples ci-dessous sont
des exemples connus bons, pas des defaults imposes par le repo.

Exemple Apple CoreML :

```bash
curl -X POST http://localhost:8100/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "apple-coreml:qwen3.5-4b-onnx-q4f16",
    "messages": [{"role": "user", "content": "Resume ce chapitre en 5 lignes"}],
    "temperature": 0.2,
    "max_tokens": 512
  }'
```

Exemple Ollama :

```bash
curl -X POST http://localhost:8100/v1/chat/completions \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ollama:qwen2.5:1.5b",
    "messages": [{"role": "user", "content": "Propose un plan de scene"}]
  }'
```

Smoke minimal utile a `ai-novel-engine` :

```bash
bash scripts/smoke_openai_compat_ane.sh \
  --url http://localhost:8100 \
  --model "apple-coreml:qwen3.5-4b-onnx-q4f16"
```

Notes :

- le endpoint est synchrone et non-streaming en v1
- `response_format` est accepte, mais pour `apple-coreml` et `ollama` le JSON doit
  rester impose par prompt
- si `MASCARADE_API_KEY` est vide, la route reste ouverte en local comme les autres
  routes protegees du core

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

### Compat legacy Notion

Hors scope operateur actif. Ce chemin reste seulement pour compatibilite legacy si
vous devez relire un ancien flux `Notion` :

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

### GitHub dispatch

Si `KILL_LIFE_GITHUB_TOKEN` ou `GITHUB_TOKEN` est configure :

```bash
# Lister les workflows allowlistes exposes par le MCP / bridge
python3 /home/clems/Kill_LIFE/tools/github_dispatch_mcp_smoke.py --json

# Ou tester le bridge API cote mascarade sans dispatch reel
curl -X POST http://localhost:3100/api/killlife/workflows/repo_state/run \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"github","dry_run":true}'
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
bash scripts/bootstrap_python_env.sh
bash scripts/test_python.sh
```

Le chemin supporte pour les tests Python du repo est `core/.venv`. Ne lance pas `python3 -m pytest` depuis l'hote sans passer par ce venv.
Le bootstrap couvre aussi les dependances du `deploy/ops_agent`, afin que le meme venv suffise pour les tests `core/tests/` qui importent l'ops-agent.
Pour une verification type "machine fraiche" sans toucher au venv principal:

```bash
bash scripts/test_python.sh --bootstrap --venv-dir /tmp/mascarade-core-venv
```

---

## Structure du projet

```
mascarade/
├── core/                             # Python FastAPI (port 8100)
│   ├── mascarade/
│   │   ├── server.py                 # Routes FastAPI + lifespan
│   │   ├── config.py                 # Settings (.env)
│   │   ├── auth.py                   # Bearer token auth
│   │   ├── cluster.py                # Coordination multi-noeud
│   │   ├── agents/
│   │   │   ├── base.py               # Dataclass Agent
│   │   │   ├── registry.py           # Registre + persistance JSON
│   │   │   ├── skills.py             # 9 agents built-in
│   │   │   ├── kicad_agent.py        # Agent KiCad
│   │   │   └── spice_agent.py        # Agent SPICE
│   │   ├── router/
│   │   │   ├── router.py             # Routeur intelligent + cache/LB/fallback
│   │   │   └── providers/            # Claude, OpenAI, Mistral, Bedrock,
│   │   │       └── ...               #   Google, HF, Ollama, Apple CoreML
│   │   ├── orchestrator/engine.py    # Sequential / parallel / pipeline
│   │   ├── integrations/
│   │   │   ├── notion.py             # Client Notion async
│   │   │   └── comfyui.py            # Generation d'images ComfyUI
│   │   ├── observability/            # OpenTelemetry, traces agents
│   │   ├── cache/                    # Cache reponses (TTL 1h)
│   │   ├── metrics/                  # Tracking usage/perf/couts
│   │   └── load_balancer/            # Distribution round-robin
│   ├── tests/                        # pytest (42 tests)
│   └── pyproject.toml
├── api/                              # TypeScript Hono (port 3100)
│   ├── src/
│   │   ├── index.ts                  # App + middleware (CORS, auth, rate-limit)
│   │   └── routes/                   # health, agents, cluster, notion, comfyui,
│   │       └── ...                   #   ops, killlife
│   └── package.json
├── web/                              # Frontend React (subtree -> crazy_life)
├── finetune/                         # Pipeline fine-tuning QLoRA
│   ├── model_selector.py             # Selection automatique de modele (HF Hub)
│   ├── train_local.py                # Entrainement GPU (4-bit QLoRA)
│   ├── train_cpu.py                  # Entrainement CPU (fallback)
│   ├── train_all.sh                  # Batch dashboard multi-domaines
│   ├── pipeline.py                   # train -> merge -> GGUF -> Ollama
│   ├── batch_local.py                # Orchestration distillation + training
│   ├── datasets/                     # Builders + datasets JSONL
│   └── kicad_*/                      # Submodules KiCad (KiC-AI, MCP, Fab Toolkit)
├── deploy/                           # Dockerfiles (core, api, edge-proxy, audio)
│   ├── cad/                          # Stack CAD (KiCad, FreeCAD, PlatformIO)
│   └── update.sh                     # Deploiement VM
├── scripts/                          # Automation (setup, deploy, finetune, CAD)
├── docs/                             # Architecture, audits, runbooks, plans
├── tools/                            # htop repo-local, litellm config
├── vendors/                          # Submodule kicadrouterai (HuggingFace)
├── setup                             # Installeur TUI interactif
├── config                            # Reconfiguration .env
├── docker-compose.yml                # Genere par setup
├── .env.example                      # Template configuration
└── CLAUDE.md                         # Conventions dev
```

## Etat auto-synchronise
## Etat auto-synchronise
<!-- AUTO-SYNC:MASCARADE-README:START -->
- dernier cycle ANE automatise: 2026-03-09T06:53:02+00:00
- etat de reference ANE: aucun accepted, meilleur diagnostic: apple-coreml:qwen2.5-0.5b-instruct-onnx
- prochain lot utile cote pipeline: Analyser les runs ayant atteint gate/repair puis resserrer la reference locale autour des meilleurs candidats.
<!-- AUTO-SYNC:MASCARADE-README:END -->

## P2P Secure Sync

For secure peer-to-peer synchronization of environment files and API keys:

- [P2P Sync Documentation](P2P_SYNC_README.md)
- [Deployment Guide](P2P_NETWORK_README.md#deployment-scenarios)

Features:
- 8-character public key authentication
- 32-character auth tokens
- AES-256 encryption for secrets
- Rsync-based efficient transfers
