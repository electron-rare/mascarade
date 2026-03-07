# TODO - Fine-Tuning Local

Etat de reference au 6 mars 2026.
Mis a jour apres audit croise code/docs le 7 mars 2026.

## 1. Ce qui est deja en place

- [x] Pipeline local `distill -> merge -> train`
- [x] Distillation teacher via Mascarade local (`127.0.0.1:3100` / `127.0.0.1:8100`)
- [x] Support CPU et GPU local
- [x] Defaut GPU / student principal = `Qwen/Qwen2.5-Coder-1.5B-Instruct`
- [x] Fallback CPU canonique = `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- [x] Smoke tests reels distillation valides sur `esp32`, `spice`, `pio`
- [x] Queue GPU et garde-fous VRAM dans `finetune/batch_local.py`
- [x] Scripts shell de lancement et de debug
- [x] `finetune/model_selector.py` disponible comme outil experimental local

## 2. Implemente depuis le dernier TODO (verifie par audit)

- [x] `batch_status.py` distingue correctement `distill` et `train` par domaine
- [x] `--resume` fonctionne: `load_resume_manifest()`, skip des domaines completed
- [x] `selected_model.json` lu par `run_local.py` au boot via `resolve_model()`
- [x] Export GGUF complet dans `pipeline.py` (`step_gguf()`): q4_k_m, q4_k_s, q5_k_m, q8_0
- [x] Deploy GGUF vers Ollama dans `pipeline.py` (`step_deploy()`): docker cp/exec + test inference
- [x] Unload Ollama model (keep_alive=0) avant training parallele GPU

Politique active de stabilisation machine:
- [x] Stopper les lanes CPU paralleles en cours quand la RAM/swap passe sous pression
- [x] Repasser `finetune/train_parallel.sh` en serie par defaut sur cette machine
- [x] Garder tout override `--parallel > 1` derriere `MASCARADE_ALLOW_PARALLEL_CPU=1`

## 3. Backlog reel

### Priorite immediate
- [ ] Valider un run batch complet jusqu'a `train=completed`
- [ ] Ecrire la commande standard de reprise `--resume` dans la doc operateur (code OK, doc manquante)

### Priorite suivante
- [ ] Comparer `max_parallel_gpu_trains=1` vs `2` sur Quadro P2000
- [ ] Mesurer temps total, VRAM libre et stabilite
- [ ] Decider si `2` slots GPU restent supportes ou seulement experimentaux

### Stabilisation dataset
- [ ] Ajouter un garde-fou de prevalidation source avant lancement batch (actuellement: existence check seulement)
- [ ] Rendre explicite dans les logs quand la normalisation corrige les IDs manquants
- [ ] Ajouter un rapport court sur `source_rows`, `distilled_rows`, `merged_rows`

### Apres stabilisation
- [ ] Integrer les modeles valides dans Mascarade (pipeline GGUF pret, pas de modele promu)
- [ ] Evaluer `Agent Zero` hors du pipeline critique
- [ ] Integrer `selected_model.json` dans `batch_local.py` (actuellement hardcode via --student-model)
- [ ] Benchmarker `model_selector.py` vs selection manuelle sur cette machine

## 4. Ordre recommande

1. Finir un batch `esp32 spice pio` avec training reel.
2. Ecrire la doc operateur `--resume`.
3. Mesurer `gpu_slots=1` puis `gpu_slots=2`.
4. Geler un runbook operateur.
5. Revenir sur les sujets exploratoires.
