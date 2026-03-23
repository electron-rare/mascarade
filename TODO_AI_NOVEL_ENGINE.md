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
- [x] P0 Detection MetalGPUError non-retryable dans le provider Ollama (commit `cab1ac4`)
- [x] P1 Contrainte single-model Apple documentee dans le code + logging des model switches (commit `cab1ac4`)
- [x] P0 Fix dead code dans Router.__init__ qui empechait l'enregistrement des providers (commit `0074272`)
- [x] P0 Baselines completes via Mascarade le 2026-03-23:
  - `apple-coreml:qwen3.5-4b-onnx-q4f16` -> **accepted** (inference PASS, structure PASS, rewrite PASS, ~1.5 tok/s)
  - `apple-coreml:qwen2.5-0.5b-instruct-onnx` -> **quality_blocked** (inference PASS, structure FAIL markdown wrap, rewrite PASS avec hallucinations, ~3.8 tok/s)
  - `apple-coreml:stateful-mistral7b-instruct-int4-coreml` -> **blocked** (timeout >300s sur inference simple, <0.1 tok/s, inutilisable sur cette machine)

## Actif
- [x] P0 Garder l'installation/staging Apple de `qwen2.5-0.5b-instruct-onnx`, `qwen3.5-4b-onnx-q4f16` et `stateful-mistral7b-instruct-int4-coreml` comme prerequis explicite du cycle ANE
- [x] P0 Finir le lot `baselines` pour `qwen2.5-0.5b-instruct-onnx` et `qwen2.5:1.5b`
- [x] P0 Stabiliser un second modele local autour de la reference Apple 4B; la cible prioritaire est un modele ONNX 4B+ compatible ANE
  - `onnx-community/Qwen3-4B-Instruct-2507-ONNX` q4f16 telecharge et valide le 2026-03-23
  - Baselines: inference PASS 38s/71tok, structure PASS (tronque), rewrite PASS 21s/150tok
  - ~3.9 tok/s vs ~1.5 tok/s pour l'ancienne ref — **3x plus rapide, meilleure qualite prose**
  - Fix tokenizer: `extra_special_tokens` converti de list en dict (incompatibilite transformers)
  - **Nouveau modele de reference locale**: `qwen3-4b-instruct-2507-q4f16`
- [ ] P1 Faire passer au moins un cycle `python3 scripts/run_next_lots.py --lot priority_models` sans checkpoint runtime inattendu
- [x] P1 Rendre explicite dans le runtime Apple qu'un seul `model_id` est servi a la fois
- [x] P1 Fixer ou contourner proprement le crash Metal du host `ollama` natif quand `qwen2.5:1.5b` est charge directement sur cette machine
  - Contourne: MetalGPUError detecte et fail-fast, Ollama delegue au P2P (VM), pas en local

## Bloque
- [x] P1 `stateful-mistral7b-instruct-int4-coreml` -> **disqualifie** sur cette machine: timeout systematique >300s, <0.1 tok/s sur Neural Engine
- [x] P1 `apple-coreml:qwen2.5-0.5b-instruct-onnx` -> baselines terminees, verdict `quality_blocked` (hallucinations prose, JSON dans markdown)
- [x] P1 Le host `ollama` natif 0.17.7 renvoie une erreur Metal -> detecte par MetalGPUError, Ollama passe par P2P vers la VM
- [x] P1 Le runtime Apple local ne sert qu'un seul `model_id` a la fois -> documente dans le code, logging des switches

## Resolu / Ferme
- [x] `ollama:qwen2.5:7b` atteint `gate`, reste `quality_blocked` sur `outline_like` -> Ollama delegue au P2P, pas en local
- [x] `ollama:qwen2.5:1.5b` reste a requalifier -> Ollama delegue au P2P, pas en local

## Prochain ordre
- [x] P0 Garder `apple-coreml:qwen3.5-4b-onnx-q4f16` comme unique reference ANE locale
  - Remplace par `apple-coreml:qwen3-4b-instruct-2507-q4f16` (3x plus rapide, meilleure qualite)
- [ ] P1 Laisser `ai-novel-engine` finir `priority_models` avec la nouvelle reference 4B
- [ ] P1 Chercher un modele ONNX 7B+ compatible CoreML plus rapide que mistral-7b (ex: Phi-3.5-mini-instruct-onnx en backup)
- [ ] P2 Tester un modele 1-2B ONNX de meilleure qualite que qwen2.5-0.5b pour les baselines vitesse

## Auto-sync
<!-- AUTO-SYNC:MASCARADE-TODO:START -->
- dernier cycle ANE automatise: 2026-03-23T12:14:00+00:00
- reference locale: apple-coreml:qwen3-4b-instruct-2507-q4f16 (**nouveau**, 3x plus rapide)
- ancienne reference: apple-coreml:qwen3.5-4b-onnx-q4f16 (remplacee)
- quality_blocked: apple-coreml:qwen2.5-0.5b-instruct-onnx (hallucinations, JSON markdown wrap)
- disqualifie: apple-coreml:stateful-mistral7b-instruct-int4-coreml (timeout >300s)
- blocage runtime principal: aucun — nouvelle reference validee
- checkpoint runtime manuel: runtime Apple arrete, modeles decharges.
- ollama: delegue au P2P (VM 192.168.0.119), pas en local (Metal crash)
<!-- AUTO-SYNC:MASCARADE-TODO:END -->
