# Runbook Apple LLM local

Runbook court pour le runtime Apple local expose sur `:8201` et route par `mascarade`.

## Qualification au 8 mars 2026
- `qwen3.5-4b-onnx-q4f16` : preflight OK puis smoke ANE `accepted` de bout en bout sous protocole courant
- `qwen2.5-0.5b-instruct-onnx` : rerun baseline en cours; utiliser surtout comme candidat vitesse Apple
- `stateful-mistral7b-instruct-int4-coreml` : preflight OK, mais smoke ANE bloque a `structure` pendant plus de 8 minutes avec les budgets de smoke; a traiter comme `preflight_only` sur cette machine
- le runtime Apple local ne sert qu'un seul `model_id` a la fois sur `:8201`

## Prerequis
- un modele explicite stage et configure via `APPLE_LLM_MODEL_ID`
- `scripts/run_apple_llm_service.sh` lance sans erreur
- le core `mascarade` repond sur `:8100`

## Checkpoint semi-auto ANE

Quand `ai-novel-engine` pilote un cycle via `python3 scripts/run_next_lots.py`, il ne restart ni ne switch le runtime Apple de force.
Il prepare la commande suivante via `scripts/prepare_runtime_step.sh`, puis attend la reprise.

Exemple:

```bash
bash scripts/prepare_runtime_step.sh \
  --apple-model qwen3.5-4b-onnx-q4f16 \
  --resume-state /chemin/vers/automation/state/next_lots_state.json \
  --ane-script /chemin/vers/ai-novel-engine/scripts/run_next_lots.py
```

## Checks de base
```bash
curl -fsS http://127.0.0.1:8201/health
curl -fsS http://127.0.0.1:8201/models
bash scripts/smoke_apple_llm.sh --url http://127.0.0.1:8201 --model "$APPLE_LLM_MODEL_ID"
```

Attendus minimaux:
- `runtime_ready: true`
- `model_loaded: true`
- le `model_id` attendu est present dans `/models`
- `POST /generate` repond
- si tu changes de modele Apple, redemarre `:8201` avant tout preflight ANE

Note:
- pour `onnx-coreml`, `scripts/run_apple_llm_service.sh` privilegie maintenant Python 3.12 sur cette machine; c'est requis pour installer proprement `onnxruntime` et `numpy` recents
- un fallback ANE vers un autre modele Apple ne peut pas fonctionner au milieu d'un meme smoke si `:8201` sert encore l'ancien `model_id`
- le protocole courant ANE evite maintenant ce switch implicite; si un autre modele Apple est requis, il faut relancer `:8201` explicitement

## Warm-up long attendu
- le premier chargement du `mlpackage` peut etre long
- tant que la requete finit et que `/health` reste coherent, ce n'est pas un echec
- pour les smokes via le core, partir avec `APPLE_LLM_TIMEOUT_SECONDS=900`
- avant de lancer un smoke chapitre ANE, faire d'abord un smoke court OpenAI-compatible via le core:

```bash
bash scripts/smoke_openai_compat_ane.sh \
  --url http://127.0.0.1:8100 \
  --model "apple-coreml:${APPLE_LLM_MODEL_ID}" \
  --timeout 600
```

## Validation bout-en-bout ANE
Depuis `ai-novel-engine`:

```bash
./scripts/smoke_local_generation.sh \
  --base-url http://127.0.0.1:8100 \
  --model "apple-coreml:${APPLE_LLM_MODEL_ID}" \
  --approve
```

Attendus:
- `meta.json` termine soit en `status=accepted`, soit en `status=quality_blocked`
- si le runtime ne tient pas une requete longue, le run sera classe `provider_failed`
- `gate_v1.json` est la reference immediate pour comprendre un blocage qualite cote ANE

## Recovery si le service garde une connexion pendante
1. Verifier d'abord si le core repond encore:
```bash
curl -fsS http://127.0.0.1:8100/health
```
2. Si `:8201` ne repond plus ou reste bloque, lister le process uvicorn:
```bash
pgrep -af "uvicorn app:app"
```
3. Arreter le service Apple si necessaire:
```bash
pkill -f "uvicorn app:app"
```
4. Relancer proprement:
```bash
bash scripts/run_apple_llm_service.sh
```
5. Rejouer ensuite:
```bash
bash scripts/smoke_apple_llm.sh --url http://127.0.0.1:8201 --model "$APPLE_LLM_MODEL_ID"
bash scripts/smoke_openai_compat_ane.sh --url http://127.0.0.1:8100 --model "apple-coreml:${APPLE_LLM_MODEL_ID}"
```
6. Si le core garde un etat stale apres recovery Apple:
```bash
docker compose restart core api
```

## Notes operatoires
- le chemin `coreml` prefere Python 3.12 pour `coremltools`
- le chemin `onnx-coreml` doit lui aussi preferer Python 3.12 sur cette machine
- `ai-novel-engine` ne doit pas parler directement a `:8201`; il passe par `POST /v1/chat/completions` sur `:8100`
- pour `ollama`, utiliser un runbook distinct; ce document est limite au chemin Apple local
- sous garde-fou ANE, `qwen3.5-4b-onnx-q4f16` est aujourd'hui la reference Apple locale; `qwen2.5-0.5b-instruct-onnx` reste utile comme baseline vitesse ou diagnostic rapide

## Etat auto-synchronise
## Etat auto-synchronise
<!-- AUTO-SYNC:MASCARADE-RUNBOOK:START -->
- dernier cycle ANE automatise: 2026-03-09T06:53:02+00:00
- meilleurs candidats actuels: aucun
- prochain lot utile cote ANE: Analyser les runs ayant atteint gate/repair puis resserrer la reference locale autour des meilleurs candidats.
- checkpoint runtime manuel: Le runtime Apple sert `qwen2.5-0.5b-instruct-onnx` au lieu de `stateful-mistral7b-instruct-int4-coreml`.
<!-- AUTO-SYNC:MASCARADE-RUNBOOK:END -->
