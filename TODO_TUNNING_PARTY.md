# TODO - Fine-Tuning Local

Etat de reference au 6 mars 2026.

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

## 2. Ce qui est obsolete dans l'ancien TODO

- [x] "Installer l'environnement Python" n'est plus un sujet principal
- [x] "Collecter les datasets initiaux" n'est plus le prochain blocage
- [x] "Creer scripts de fine-tuning avec LoRA" est deja fait
- [x] "Verifier acces GPU" est deja fait

## 3. Backlog reel

### Priorite immediate
- [ ] Valider un run batch complet jusqu'a `train=completed`
- [x] Ajouter un resume simple des manifests batch (`finetune/batch_status.py`)
- [ ] Ecrire la commande standard de reprise `--resume` dans la doc operateur

### Priorite suivante
- [ ] Comparer `max_parallel_gpu_trains=1` vs `2` sur Quadro P2000
- [ ] Mesurer temps total, VRAM libre et stabilite
- [ ] Decider si `2` slots GPU restent supportes ou seulement experimentaux

### Stabilisation dataset
- [ ] Ajouter un garde-fou de prevalidation source avant lancement batch
- [ ] Rendre explicite dans les logs quand la normalisation corrige les IDs manquants
- [ ] Ajouter un rapport court sur `source_rows`, `distilled_rows`, `merged_rows`

### Apres stabilisation
- [ ] Export GGUF des meilleurs runs
- [ ] Integrer les modeles valides dans Mascarade
- [ ] Evaluer `Agent Zero` hors du pipeline critique
- [ ] Decider si `selected_model.json` doit etre lu par `run_local.py` / `batch_local.py`
- [ ] Benchmarker `model_selector.py` vs selection manuelle sur cette machine

## 4. Ordre recommande

1. Finir un batch `esp32 spice pio` avec training reel.
2. Ajouter un resume d'etat batch.
3. Mesurer `gpu_slots=1` puis `gpu_slots=2`.
4. Geler un runbook operateur.
5. Revenir sur les sujets exploratoires.
