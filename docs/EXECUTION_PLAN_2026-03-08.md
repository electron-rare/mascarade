# Plan d'execution - 8 mars 2026

Plan de reference pour `mascarade` apres revalidation ANE avec garde-fou.

Le plan du 7 mars 2026 reste archive. La priorite ANE est maintenant la
stabilite runtime utile a un protocole qualite, pas seulement le preflight.

Pilotage operationnel:
- le driver ANE de reference est `python3 scripts/run_next_lots.py --lot <lot>` cote `ai-novel-engine`
- les checkpoints semi-autos passent par `scripts/prepare_runtime_step.sh`
- la verification ou l'installation des modeles Apple requis passe par `scripts/ensure_apple_models.sh`

## Axe 1 - AI Novel Engine integration

### Etat constate
- le shim `POST /v1/chat/completions` est livre et stable
- le chemin Ollama de reference pour ANE est le service Docker CPU, pas le host natif Metal
- `OLLAMA_TIMEOUT_SECONDS` est maintenant configurable pour les requetes longues ANE
- `apple-coreml:qwen3.5-4b-onnx-q4f16` est `accepted` sous protocole ANE courant
- `ollama:qwen2.5:7b` atteint `gate`, exerce `repair`, puis reste `quality_blocked`
- le lot `baselines` est en cours pour `qwen2.5-0.5b-instruct-onnx` et `qwen2.5:1.5b`
- `stateful-mistral7b-instruct-int4-coreml` reste `preflight_only`
- le runtime Apple local n'expose qu'un seul `model_id` a la fois sur `:8201`

### Prochain lot recommande
0. Verifier ou restager explicitement les modeles Apple cibles avant toute revalidation ANE:
   - `qwen2.5-0.5b-instruct-onnx`
   - `qwen3.5-4b-onnx-q4f16`
   - `stateful-mistral7b-instruct-int4-coreml`
1. Garder `apple-coreml:qwen3.5-4b-onnx-q4f16` comme reference locale ANE tant qu'il reste `accepted`.
2. Garder `ollama` via Docker CPU comme reference runtime pour ANE tant que le host Metal reste casse.
3. Finir le lot `baselines`, puis laisser `ai-novel-engine` ajuster `rewrite` ou `repair` pour sortir `qwen2.5:7b` de `outline_like`.
4. Documenter explicitement la contrainte "un seul modele Apple a la fois" pour les smokes ANE.

## Axe 2 - Cockpit / Observability

### Position
- le chantier cockpit et observability continue, mais reste decouple du besoin ANE immediat
- ne pas remelanger les validations ANE avec le lot cockpit tant que la reference `accepted` Apple 4B n'a pas ete reconfirmee sur un second cycle

## Axe 3 - Fine-tuning local

### Position
- chantier inchange
- priorite secondaire tant qu'ANE n'a pas de reference locale stable sous garde-fou

## Auto-sync
<!-- AUTO-SYNC:MASCARADE-PLAN:START -->
- dernier cycle ANE automatise: 2026-03-23T21:34:05+00:00
- reference locale ANE: mistral:mistral-large-latest
- prochain lot ANE a servir: Reference locale reconfirmee; retablir le runtime des modeles provider_failed avant de poursuivre.
<!-- AUTO-SYNC:MASCARADE-PLAN:END -->
