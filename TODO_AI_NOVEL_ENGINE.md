# TODO AI Novel Engine - Mascarade

Backlog dedie a l'integration `ai-novel-engine`.

Regle:
- ne suivre ici que les sujets runtime, API et serving local utiles a `ai-novel-engine`
- laisser cockpit, observability, fine-tuning et le reste dans les backlogs globaux deja existants
- mettre a jour `docs/EXECUTION_PLAN_2026-03-08.md` si l'ordre reel change

## Deja implemente
- [x] P0 Shim OpenAI-compatible `POST /v1/chat/completions`
- [x] P0 Mapping `model=apple-coreml:<id>` et `model=ollama:<id>`
- [x] P0 Reponse OpenAI-compatible minimale suffisante pour `ai-novel-engine`
- [x] P0 Tests du shim OpenAI-compatible
- [x] P0 Documentation de branchement local dans le `README`
- [x] P1 Smoke script minimal `scripts/smoke_openai_compat_ane.sh`
- [x] P1 Runbook Apple local `docs/RUNBOOK_APPLE_LLM_LOCAL.md`
- [x] P1 Message d'erreur Apple local explicite sur timeout long et suppression du retry aveugle sur `ReadTimeout`
- [x] P0 Validation `ollama` avec `ai-novel-engine` via `ollama:qwen2.5:1.5b`
- [x] P0 Validation Apple locale sequentielle ANE avec `qwen2.5-0.5b-instruct-onnx`
- [x] P0 Validation Apple locale sequentielle ANE avec `qwen3.5-4b-onnx-q4f16`
- [x] P1 Le launcher `scripts/run_apple_llm_service.sh` prefere aussi Python 3.12 pour `onnx-coreml`
- [x] P1 Timeout Ollama configurable via `OLLAMA_TIMEOUT_SECONDS`
- [x] P1 Message d'erreur Ollama explicite sur timeout long
- [x] P0 Helper `scripts/ensure_apple_models.sh` pour verifier ou installer les trois modeles Apple requis du cycle ANE
- [x] P0 Helper `scripts/prepare_runtime_step.sh` pour preparer les checkpoints semi-autos de restart/switch runtime
- [x] P0 Revalidation ANE avec garde-fou:
  - `ollama:qwen2.5:1.5b` -> `quality_blocked`
  - `apple-coreml:qwen2.5-0.5b-instruct-onnx` -> `quality_blocked`
  - `apple-coreml:qwen3.5-4b-onnx-q4f16` -> `provider_failed`
  - `ollama:qwen2.5:7b` -> `provider_failed`
- [x] P0 Rerun post-durcissement prose:
  - `ollama:qwen2.5:1.5b` redevient complet jusqu'a `gate`
  - `apple-coreml:qwen2.5-0.5b-instruct-onnx` redevient complet jusqu'a `gate`
- [x] P0 Revalidation ANE sous protocole `gate + repair` borne a `300s` par requete:
  - `ollama:qwen2.5:1.5b` -> `failed_stage=structure`
  - `apple-coreml:qwen2.5-0.5b-instruct-onnx` -> `failed_stage=rewrite`
  - `apple-coreml:qwen3.5-4b-onnx-q4f16` -> `failed_stage=rewrite`
  - `ollama:qwen2.5:7b` -> `failed_stage=rewrite`

## Actif
- [ ] P0 Garder l'installation/staging Apple de `qwen2.5-0.5b-instruct-onnx`, `qwen3.5-4b-onnx-q4f16` et `stateful-mistral7b-instruct-int4-coreml` comme prerequis explicite du cycle ANE
- [ ] P0 Finir le lot `baselines` pour `qwen2.5-0.5b-instruct-onnx` et `qwen2.5:1.5b`
- [ ] P0 Stabiliser un second modele local autour de la reference Apple 4B; la cible prioritaire est `ollama:qwen2.5:7b`
- [ ] P1 Faire passer au moins un cycle `python3 scripts/run_next_lots.py --lot priority_models` sans checkpoint runtime inattendu
- [ ] P1 Rendre explicite dans le runtime Apple qu'un seul `model_id` est servi a la fois
- [ ] P1 Fixer ou contourner proprement le crash Metal du host `ollama` natif quand `qwen2.5:1.5b` est charge directement sur cette machine

## Bloque
- [ ] P1 `stateful-mistral7b-instruct-int4-coreml` repond au preflight, mais le smoke ANE est reste bloque a `structure` plus de 8 minutes avec les budgets reduits de smoke
- [ ] P1 `ollama:qwen2.5:7b` atteint maintenant `gate`, mais reste `quality_blocked` sur `outline_like` apres deux passes `repair`
- [ ] P1 `apple-coreml:qwen2.5-0.5b-instruct-onnx` demande encore un switch runtime explicite pour finir son rerun baseline
- [ ] P1 `ollama:qwen2.5:1.5b` reste a requalifier une fois le lot `baselines` repris jusqu'au bout
- [ ] P1 Le host `ollama` natif 0.17.7 renvoie une erreur Metal sur `qwen2.5:1.5b`; la validation locale ANE s'appuie pour l'instant sur un service Docker CPU expose sur `127.0.0.1:11435`
- [ ] P1 Le runtime Apple local ne sert qu'un seul `model_id` a la fois sur `:8201`, ce qui bloque un fallback ANE entre deux modeles Apple au sein d'un meme smoke

## Prochain ordre
- [ ] P0 Garder `apple-coreml:qwen3.5-4b-onnx-q4f16` comme reference ANE locale actuelle tant qu'un autre modele ne passe pas `accepted`
- [ ] P0 Garder `ollama` via Docker CPU comme chemin de reference pour les candidats Ollama tant que le host Metal reste casse
- [ ] P1 Exposer plus clairement la contrainte "un seul modele Apple a la fois" dans les runbooks et le runtime
- [ ] P1 Laisser `ai-novel-engine` finir `baselines`, puis rejouer `ollama:qwen2.5:7b` apres ajustement de `rewrite` ou `repair`
- [ ] P1 Ne requalifier `qwen2.5-0.5b` et `qwen2.5:1.5b` qu'en baselines vitesse tant qu'ils n'ont pas un verdict courant complet

## Auto-sync
<!-- AUTO-SYNC:MASCARADE-TODO:START -->
- dernier cycle ANE automatise: 2026-03-13T14:15:56+00:00
- accepted via runtime local: apple-coreml:qwen3.5-4b-onnx-q4f16
- gate atteint via runtime local: apple-coreml:qwen3.5-4b-onnx-q4f16, ollama:qwen2.5:7b, apple-coreml:qwen2.5-0.5b-instruct-onnx, ollama:qwen2.5:1.5b
- blocage runtime principal: Confirmer la reference accepted puis resserrer rewrite/repair sur les modeles deja bloques a gate.
<!-- AUTO-SYNC:MASCARADE-TODO:END -->
