# TODO - Fine-Tuning Local

Etat de reference au 6 mars 2026.
Mis a jour apres audit croise code/docs le 7 mars 2026.
Recale sur l'etat reel des runs locaux le 8 mars 2026.

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
- [x] `batch_local.py` force maintenant le `line_buffering` en mode non interactif
  - effet attendu: les messages `[WAIT] GPU memory busy` et les transitions train deviennent visibles tout de suite dans une session shell non-TTY
- [x] Un verrou GPU global machine a ete ajoute dans `run_local.py`
  - but: `gpu_slots=1` veut maintenant dire "un seul train GPU global a la fois" entre `batch_local.py`, `bench_gpu_slots.py` et les lancements manuels
  - propagation explicite du nombre de slots via `MASCARADE_GPU_GLOBAL_SLOTS`
- [x] `--resume` recupere maintenant les etats `running` orphelins
  - si le pid n'existe plus et que le child manifest n'est pas termine proprement, le domaine repasse en `pending`
  - si le child manifest est deja `completed`, le domaine est marque `completed` a la reprise
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
- [x] Ecrire la commande standard de reprise `--resume` dans la doc operateur (README batch local mis a jour)

### Differe post-stabilisation
- [ ] Valider un run batch complet jusqu'a `train=completed`
  - run de reprise retenu: `finetune/runs/p2000_bench_gpu1_fixed_20260308_143343`
  - commande canonique de reprise:
    `python finetune/batch_local.py --resume finetune/runs/p2000_bench_gpu1_fixed_20260308_143343`
  - correctif applique le `8 mars 2026`: garde-fou `tf32` dans `finetune/train_local.py` pour eviter l'erreur `--tf32 requires Ampere` sur Quadro P2000

### Priorite suivante
- [x] Comparer `max_parallel_gpu_trains=1` vs `2` sur Quadro P2000
- [x] Mesurer temps total, VRAM libre et stabilite
- [x] Decider si `2` slots GPU restent supportes ou seulement experimentaux
  - rapport: `docs/GPU_SLOT_BENCH_P2000_2026-03-08.md`
  - `slots=1`: `1984.09 s`
  - `slots=2`: `1318.06 s`
  - gain observe: `33.6 %`
  - decision: `2` slots valides pour `TinyLlama 1.1B / seq_len=256 / 64 samples`, sous garde-fou VRAM

### Stabilisation dataset
- [x] Ajouter un garde-fou de prevalidation source avant lancement batch (validation apres normalisation autorisee)
- [x] Rendre explicite dans les logs quand la normalisation corrige les IDs manquants
- [x] Ajouter un rapport court sur `source_rows`, `distilled_rows`, `merged_rows` (`dataset_report.json`)

### Apres stabilisation
- [x] Integrer les modeles valides dans Mascarade (registre local de promotion + premier modele promu)
  - premier alias promu: `esp32_local_v1`
- [ ] Evaluer `Agent Zero` hors du pipeline critique
- [x] Integrer `selected_model.json` dans `batch_local.py` (override explicite `--student-model` conserve)
- [x] Benchmarker `model_selector.py` vs selection manuelle sur cette machine (rapport heuristique: `docs/MODEL_SELECTOR_BENCH_2026-03-08.md`)

## 4. Ordre recommande

1. Finir `p2000_bench_gpu1_fixed_20260308_143343` jusqu'a `train=completed`.
2. Promouvoir au moins un deuxieme domaine valide (`spice` ou `pio`) si le batch canonique termine vert.
3. Decider si une exportation GGUF doit accompagner l adapter promu.
4. Revenir sur `Agent Zero` hors du pipeline critique.
5. Revenir sur les sujets exploratoires.
