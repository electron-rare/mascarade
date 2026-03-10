# Fine-Tuning Pipeline — Mascarade

Fine-tune des modèles LLM spécialisés pour les skills électronique/hardware/IoT et les déployer via Ollama.

Lecture recommandee:

- runbook operateur: `docs/FINETUNING_OPERATOR_RUNBOOK.md`
- cheatsheet rapide: `docs/FINETUNING_CHEATSHEET_2026-03-06.md`
- recap methodes / etat de l art 2026: `docs/FINETUNING_ETAT_DE_L_ART_2026-03-06.md`
- plan 4090 / scheduling parallele: `docs/FINETUNING_4090_PARALLEL_PLAN.md`
- shortlist modeles 2026: `docs/FINETUNING_MODEL_SHORTLIST_2026-03-08.md`

## Quick Start Local

Depuis la racine du repo:

```bash
. ./scripts/llm_env.sh
./scripts/bootstrap_finetune_env.sh
source venv_tuning/bin/activate
python test_environment.py

# Auto: GPU si dispo, sinon fallback CPU
python finetune/run_local.py stm32 --max-samples 128 --epochs 1

# Forcer le fallback CPU
python finetune/run_local.py kicad --device cpu --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --max-samples 64

# Wrapper shell equivalent
./scripts/finetune_local.sh embedded --device auto --max-samples 256

# Run jetable isole dans finetune/runs/smoke_<domain>_<timestamp>/
./scripts/finetune_local.sh stm32 --device gpu --max-samples 8 --epochs 1 --smoke

# CPU parallel helper is serialized by default on this machine
./finetune/train_parallel.sh --domains dsp,emc

# Opt-in override only when memory/swap margin has been revalidated
MASCARADE_ALLOW_PARALLEL_CPU=1 ./finetune/train_parallel.sh --parallel 2
MASCARADE_ALLOW_PARALLEL_CPU=1 ./finetune/train_parallel.sh --preset cpu3
MASCARADE_ALLOW_PARALLEL_CPU=1 ./finetune/train_parallel.sh --preset cpu4
```

Presets CPU operateur :

- `--preset cpu3`
  - `3` students CPU paralleles
  - auto-tuning avec plafond pragmatique a `6` threads par student
- `--preset cpu4`
  - `4` students CPU paralleles
  - auto-tuning avec plafond pragmatique a `5` threads par student
- override manuel :
  - `--threads-per-student 4`
  - `--no-auto-threads`

Profil operateur `28 threads / 64 Go RAM` :

- `GPU`
  - `1` pipeline principal GPU
- `CPU students`
  - `4` students paralleles
  - `4` threads par student
  - budget total `16` threads
- `Reviewer / consolidator`
  - `1` worker CPU priorite basse
  - budget cible `4` threads
- `Doctor`
  - `1` worker CPU diagnostic
  - budget cible `4` threads
- `Reserve`
  - `4` threads pour OS / I/O / TUI / marge

Commande CLI equivalente :

```bash
./scripts/start_tuning_party.sh \
  --operator-profile 28t-64g-full \
  --background \
  --verbose
```

Preset recommande pour cette machine (RTX 4090 24 Go VRAM) :

```bash
./scripts/finetune_host_gpu.sh stm32
```

Preflight `llmfit` recommande pour fiabiliser le sizing avant training :

```bash
cd /ai/saisail/llmfit
cargo +stable build --release -p llmfit

cd /ai/saisail/mascarade
python finetune/run_local.py stm32 --device gpu --max-samples 8 --epochs 1
```

Preset plus agressif pour `stm32` sur RTX 4090 :

```bash
./scripts/finetune_stm32_4090.sh
```

Preset plus agressif pour `platformio` sur RTX 4090 :

```bash
./scripts/finetune_platformio_4090.sh
```

Preset solo pour `Qwen3.5-9B-Base` sur RTX 4090 :

```bash
./scripts/finetune_qwen35_base_4090.sh
./scripts/finetune_qwen35_base_4090.sh stm32
```

Telechargement cible des modeles recents retenus par la politique auto:

```bash
. ./scripts/llm_env.sh
./scripts/download_latest_finetune_models.sh
```

Racine canonique des modeles:

- `/ai/llm`
- cache HF: `/ai/llm/huggingface/hub`
- caches locaux: `/ai/llm/models_cache`
- watch/bench: `/ai/llm/watch_models`
- Apple LLM: `/ai/llm/apple-llm`

Le flux finetuning ne doit plus telecharger de modeles dans le repo ni dans un
cache home secondaire. La migration des caches legacy se fait avec:

```bash
./scripts/migrate_models_to_llm.sh
./scripts/migrate_models_to_llm.sh --execute --cleanup --link-home-cache
```

Profil de charge multi-run sur RTX 4090 :

```bash
# 1 x Qwen3-8B + 2 x Qwen3-4B-Instruct-2507
./scripts/triple_train_4090.sh

# Meme profil, fige sur le plus haut niveau valide actuellement
./scripts/triple_train_4090_safe_max.sh

# Variante de stress plus haute, validee mais avec faible marge VRAM
MODE=triple-mixed-1024 ./scripts/triple_train_4090.sh

# Variante mixte: 8B pousse a 1024, 4B gardes a 768
MODE=triple-staggered-8b1024-4b768 ./scripts/triple_train_4090.sh

# 2 x Qwen3-8B
MODE=dual-8b-512 ./scripts/triple_train_4090.sh
```

Defaut retenu dans ce preset :

- le `teacher` n est plus fige:
  - mode auto par defaut: `--teacher-objective balanced`
  - `balanced`: `Qwen/Qwen2.5-7B-Instruct` puis `Qwen/Qwen3-4B-Instruct-2507`, avant les gros teachers offload
  - `quality`: `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` puis `Devstral 24B`, puis `Mistral 24B`
  - `fast`: `Qwen/Qwen3-4B-Instruct-2507` puis `Qwen/Qwen2.5-7B-Instruct`
  - fallback stable si rien ne passe: `ollama/qwen2.5:14b`
  - les teachers `local-hf` lourds du mode `quality` partent en `local_hf_device=auto`, pas en `cuda:0` force
- le `student` n est plus fige non plus:
  - `finetune/selected_model.json` garde la priorite s il existe
  - sinon le launcher choisit maintenant selon le hardware detecte
  - sur cette machine 24 Go, la cible auto est `Qwen/Qwen3.5-9B-Base`

Alternative generaliste plus recente :

```bash
STUDENT_MODEL=Qwen/Qwen3-4B-Instruct-2507 ./scripts/finetune_host_gpu.sh stm32
```

Alternative de fine-tuning plus recente, orientee student solo :

```bash
STUDENT_MODEL=Qwen/Qwen3.5-9B-Base ./scripts/finetune_host_gpu.sh stm32
```

Orchestration du prochain lot utile:

```bash
# run operateur canonique: recalcule la veille, prepare le benchmark watch,
# sort le report de purge et lance les smokes outilles en tmpfs
./scripts/next_finetune_lots.sh --continue-on-error

# benchmark watch explicite
./scripts/bench_watch_candidate.sh
./scripts/bench_watch_candidate.sh --execute
```

Lanceur operateur unique:

```bash
cd /ai/saisail/mascarade
./scripts/start_tuning_party.sh
./scripts/tuning_party_tui.sh
./scripts/tuning_party_tui.sh --dashboard
```

Par defaut il execute:

1. `./scripts/next_finetune_lots.sh --continue-on-error`
2. `./scripts/auto_chain_next_lots_loop.sh` en arriere-plan
3. `finetune/batch_full_pipeline.sh` au premier plan

Scripts de pilotage:

- `./scripts/status_tuning_party.sh`
- `./scripts/stop_tuning_party.sh`

Rapport vert de reference au 9 mars 2026:

- `finetune/runs/next-lots_20260309_063107/summary.json`
- `watch_refresh=ok`
- `watch_bench=ok`
- `prune=ok`
- `cad_smoke=ok`
- `components_review=ok`

Lancement en continu des lots utiles:

```bash
cd /ai/saisail/mascarade
./scripts/auto_chain_next_lots_loop.sh \
  --iterations 1 \
  --sleep-seconds 600 \
  --max-blocked-streak 12 \
  --max-cycles 0 \
  --stop-on-no-candidate
```

Le benchmark watch:

- reutilise d abord un modele deja present dans `/ai/llm`
- ne retente pas de download si un snapshot local complet existe deja
- bloque en preflight si la VRAM libre est insuffisante

Sur les presets `*_4090.sh`, le preflight GPU fait aussi un nettoyage best-effort
avant de charger les modeles:

- arret du `core` de tuning precedent s il tourne encore
- unload des modeles `ollama`
- unload des modeles `ComfyUI` via `POST /free`
- affichage d un resume VRAM avant / apres

Variables utiles:

- `TOKENIZE_WORKERS=20` par defaut sur les presets 4090
- `DISTILL_CONCURRENCY=1` par defaut
- `UNLOAD_OLLAMA_BEFORE_RUN=1` sur les presets 4090
- `UNLOAD_COMFYUI_BEFORE_RUN=1` sur les presets 4090
- `COMFYUI_API_URL=http://127.0.0.1:8188` par defaut

Exemple sans dechargement ComfyUI:

```bash
UNLOAD_COMFYUI_BEFORE_RUN=0 ./scripts/finetune_platformio_4090.sh
```

Comportement:

- `run_local.py` choisit automatiquement `train_local.py` si CUDA est utilisable
- sinon il bascule sur `train_cpu.py`
- si aucun `--model` n est force et qu aucun `selected_model.json` n existe, `run_local.py` choisit maintenant le student selon le hardware detecte
- si `datasets/<domain>_chat.jsonl` manque, le launcher genere automatiquement le seed dataset local s il existe
- `--dataset-path` permet d'entraîner sur un dataset dérivé sans écraser `datasets/<domain>_chat.jsonl`
- `--offline` force l'usage du cache Hugging Face local; en fallback CPU, le launcher attend `TinyLlama/TinyLlama-1.1B-Chat-v1.0` en cache et peut reutiliser le modele GPU par defaut s'il est deja present localement
- `--eval` est disponible uniquement sur le chemin GPU
- `--verbose` affiche plus de détails sur le launcher et le trainer
- `--quiet` réduit les logs et masque les progress bars quand c est supporté
- `--tokenize-workers 0` laisse le trainer choisir automatiquement des workers CPU pour la tokenization
- `--distill-concurrency` parallelise seulement les appels teacher; ce n est pas du multi-GPU
- sur une seule RTX 4090, garder par defaut un seul run student GPU a la fois tant qu un teacher GPU actif distille encore
- un benchmark training-only valide maintenant `2` slots students pour `Qwen/Qwen3-4B-Instruct-2507` a `seq_len=1024` sur `stm32, spice, kicad, platformio`
- `--smoke` isole les outputs temporaires sous `finetune/runs/smoke_<domain>_<timestamp>/`
- `--run-label <label>` fait la meme chose avec un prefixe explicite, sans polluer `finetune/models_local/` ou `finetune/models_cpu/`
- le pipeline refuse explicitement certains modeles `teacher-only` comme students, notamment `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` et `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8`
- les teachers Mistral / DeepSeek ajoutes a la matrice de scenarios sont eux aussi reserves au chemin teacher-only ou distillation dediee
- quand `llmfit` est disponible, `run_local.py` lance un preflight `llmfit plan <model> --context <seq_len> --json` avant le training
- ce preflight ecrit un `llmfit_plan.json` dans l `output_dir` du run, ou dans le run-dir isole si `--smoke` / `--run-label` est utilise
- le preflight `llmfit` reste un garde-fou d inference: il bloque un training GPU si meme le chemin GPU inference est juge impossible, mais il ne remplace pas les mesures VRAM reelles de QLoRA
- si `llmfit` n est pas compile, le pipeline garde le comportement precedent et logue seulement un warning
- le trainer GPU utilise maintenant par defaut un chemin plus agressif: tokenization dynamique, packing train, `NF4 + bf16` si supporte, `flash_attention_2` si disponible sinon `sdpa`
- `batch_local.py` sait maintenant ouvrir jusqu a `2` slots student, mais seulement quand le budget GPU le permet vraiment sur la machine
- avec un teacher `ollama` lourd, le scheduler garde automatiquement `1` seul student actif tant que des distills sont encore en cours
- quand la file de distillation est vide, le scheduler decharge le modele teacher via l API Ollama (`keep_alive=0`) pour recuperer la VRAM et ouvrir le deuxieme slot student
- `OLLAMA_API_URL` permet de pointer ce dechargement automatique vers un endpoint Ollama non standard
- sans `--teacher-provider` / `--teacher-model`, `batch_local.py` choisit maintenant le `teacher` selon le materiel detecte et le cache local HF disponible
- `--teacher-objective balanced` est le defaut pratique pour cette machine
- `--teacher-objective fast` privilegie un teacher `local-hf` 4B/7B en vrai compute GPU
- `--teacher-objective quality` privilegie un gros teacher `local-hf` 35B/24B en offload
- sur des domaines tres code-heavy, `Devstral 24B` peut remonter plus haut dans l ordre auto
- cette selection auto exige maintenant un vrai `cuda_available`; une simple presence de driver/GPU ne suffit plus pour choisir un teacher `local-hf` GPU
- sans `--max-parallel-gpu-trains`, `--seq-len` ou `--student-max-samples`, `batch_local.py` injecte un profil `balanced` adapte a la machine presente
- `--auto-promote` remplace automatiquement l alias live `mascarade-<domain>` seulement si `merge -> gguf -> deploy -> smoke` passent tous
- le deploy Ollama choisit maintenant automatiquement le runtime `host` ou `container`; sur cette machine, le chemin live passe par l Ollama hote car le conteneur partage un store read-only
- si le filesystem du repo est sature, la promotion stage automatiquement le merge/GGUF sous `/dev/shm/mascarade-promotion`
- si le filesystem du repo est sature, `run_local.py` et `batch_local.py` deplacent maintenant aussi les outputs de training sous `/dev/shm/mascarade-train` ou `MASCARADE_TRAIN_WORKDIR`
- nuance importante sur le stockage:
  - les outputs de training restent dans le chemin demande tant que l espace libre suffit
  - ils ne basculent vers tmpfs que quand le repo FS n a plus la marge requise
- le registre de promotion live est garde dans `finetune/models_local/promotion_registry.json` par defaut
- ces runs isoles ecrivent aussi un `run.json` avec config, paths, commande trainee et statut final
- `run_local.py` ecrit aussi un `run.json` quand un `--output-dir` explicite est fourni, meme sans `--smoke` ni `--run-label`
- le noeud racine `llmfit` de ce `run.json` expose directement le statut `validated`, `warning`, `unavailable`, `not_applicable`, `disabled` ou `rejected`
- un refus `llmfit` GPU est donc trace dans le manifest meme si le training ne demarre jamais
- les commandes stockees dans `run.json` sont redactees pour ne pas exposer de secret comme `--api-key`
- le smoke de promotion actuel valide l alias Ollama et une reponse texte domaine-specifique
  via `finetune/promotion_utils.py`
- il ne lance pas encore automatiquement un vrai workflow outille/MCP type
  `pio run`, `kicad-cli`, `FreeCADCmd` ou `OpenSCAD`
- l outillage existe maintenant en smoke operateur separe:
  - `scripts/cad_tool_smoke_tmpfs.sh`
  - `scripts/next_finetune_lots.sh`
- ce smoke outille valide aujourd hui:
  - `doctor`
  - `kicad-cli`
  - `freecad`
  - `platformio`
- `kicad_mcp` est trace `unavailable` tant que `finetune/kicad_mcp_server/package.json`
  reste absent
- `OpenSCAD` reste hors couverture automatique sur cette stack

Variables `llmfit` utiles:

- `LLMFIT_BIN=/chemin/vers/llmfit` pour forcer un binaire
- `LLMFIT_ROOT=/ai/saisail/llmfit` pour resoudre un binaire build local
- `LLMFIT_MEMORY=24G` pour forcer la VRAM si l autodetection est mauvaise
- `LLMFIT_PREFLIGHT=0` pour desactiver le preflight
- `LLMFIT_MIN_FIT=good` pour relever le seuil d alerte
- `LLMFIT_ALLOW_CARGO_RUN=1` pour autoriser un fallback `cargo run`, utile ponctuellement mais moins propre sur des runs paralleles

Validation pratique sur cette machine:

- `Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=512` passe sur la RTX 4090
- `Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=768` passe aussi sur la RTX 4090
- pic VRAM echantillonne observe en `768`: environ `20.8 Go / 24 Go`
- `Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=1024` passe aussi, mais avec une marge faible
- pic VRAM echantillonne observe en `1024`: environ `23.3 Go / 24 Go`
- benchmark training-only sur datasets deja merges:
  - `slots=1`: `78.01s`, pic VRAM `9532 MiB`
  - `slots=2`: `42.01s`, pic VRAM `17119 MiB`
  - speedup observe: `1.857x`
- promotion live validee:
  - aliases:
    - `mascarade-platformio`
    - `mascarade-stm32`
    - `mascarade-spice`
    - `mascarade-iot`
    - `mascarade-kicad`
    - `mascarade-freecad`
    - `mascarade-dsp`
    - `mascarade-embedded`
    - `mascarade-power`
    - `mascarade-emc`
  - sources:
    - `platformio_sessions-4090-parallel-750x2_20260307_040828`
    - `stm32_sessions-4090-parallel-750x2_20260307_040828`
    - `spice_sessions-4090-parallel_20260307_035624`
    - `iot_sessions-4090-parallel-750x2_20260307_040828`
    - `kicad_sessions-4090-parallel-750x2_20260307_040828`
    - `freecad_sessions-4090-parallel-750x2_20260307_040828`
    - `dsp_sessions-4090-parallel_20260307_035624`
    - `embedded_sessions-4090-parallel-750x2_20260307_040828`
    - `power_sessions-4090-parallel-750x2_20260307_040828`
    - `emc_sessions-4090-parallel-750x2_20260307_040828`
  - registre: `finetune/models_local/promotion_registry.json`
  - `mascarade-iot` est valide non seulement via `ollama run`, mais aussi via `POST /api/agents/send`
  - `mascarade-kicad` est valide non seulement via `ollama run`, mais aussi via `POST /api/agents/send`
  - `mascarade-freecad`, `mascarade-dsp` et `mascarade-embedded` sont aussi valides non seulement via `ollama run`, mais aussi via `POST /api/agents/send`
  - `mascarade-power` et `mascarade-emc` sont aussi valides non seulement via `ollama run`, mais aussi via `POST /api/agents/send`
- `Qwen/Qwen3-8B` en `seq_len=1024` avec `2 x Qwen/Qwen3-4B-Instruct-2507` en `seq_len=768` passe aussi
- pic VRAM echantillonne observe sur ce profil mixte: environ `18.6 Go / 24 Go`
- `2 x Qwen/Qwen3-8B` en `seq_len=512` ne passe pas proprement: un run finit, l autre part en `CUDA OOM`
- `scripts/triple_train_4090.sh` coupe `ComfyUI` avant le test et le relance a la fin par defaut
- `scripts/triple_train_4090_safe_max.sh` reste volontairement sur `seq_len=768`; `1024` est valide mais trop proche du plafond VRAM pour etre le preset par defaut

## Model Selector

Un helper local permet de chercher et classer des students
compatibles avec la machine, et alimente maintenant aussi le workflow auto:

```bash
python finetune/model_selector.py --help
python finetune/model_selector.py --watch --refresh --task code
python finetune/model_selector.py --auto
python finetune/model_selector.py --auto --download --validate
```

Comportement:

- l outil interroge le Hub Hugging Face, met les resultats en cache local et
  classe les modeles selon VRAM, fit fine-tuning, generation de modele,
  signaux de qualite et popularite
- `--watch` ajoute une veille web sur les releases recentes provenant d auteurs
  de confiance (`Qwen`, `mistralai`, `deepseek-ai`, `JetBrains`) et ecrit un
  `model_watch_report.json` dans le state runtime
- cette veille sert a surveiller les nouveaux candidats adaptes a nos domaines
  avant de les faire entrer dans la shortlist ou la politique auto
- il ecrit maintenant son state runtime dans un repertoire dedie, pour ne pas
  dependre du FS du repo quand il est sous pression:
  - sandbox/local: `/tmp/mascarade-finetune-state`
  - hors sandbox si disponible: `/dev/shm/mascarade-finetune-state`
  - override possible: `MODEL_SELECTOR_STATE_DIR` ou `MASCARADE_FINETUNE_STATE_DIR`
- il y ecrit un `selected_model.json` local quand un modele est choisi
- `run_local.py` et `batch_local.py` le consomment maintenant par defaut
  si aucun `--model` / `--student-model` explicite n est fourni
- si aucun student explicite n est fourni et que le run n est pas `--offline`,
  `run_local.py` et `batch_local.py` rafraichissent automatiquement la veille
  et la selection quand le cache TTL est depasse, puis tracent le
  `model_watch_report.json` utilise dans leurs manifests/logs
- `train_all.sh` reste hors de ce contrat pour l instant
- benchmark live valide au 8 mars 2026 sur cette RTX 4090:
  - artefact: `finetune/runs/model-selector-benchmark-live_20260308_213050/summary.json`
  - verdict: le selector et la politique manuelle convergent sur `Qwen/Qwen3.5-9B-Base`

## Distillation Teacher -> Student

Pour utiliser un gros modèle comme professeur et fine-tuner un petit modèle local:

```bash
# Core/API Mascarade doit être démarré avec au moins un provider configuré
# Si MASCARADE_API_KEY est present dans .env, le wrapper la recharge automatiquement.
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider ollama \
  --teacher-model qwen2.5:14b \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --smoke \
  --device gpu \
  --epochs 1
```

Ce workflow:

- lit `finetune/datasets/<domain>_chat.jsonl`
- demande au teacher de produire des variantes/distillations au format ShareGPT
- écrit un dataset distillé dans `finetune/datasets/distilled/`
- fusionne source + distillation avec déduplication
- lance ensuite `run_local.py` sur le dataset fusionné
- `--verbose` propage les logs détaillés sur la distillation, le merge et le training
- `--quiet` garde seulement les messages importants
- `--concurrency 0` sur `distill_dataset.py` choisit automatiquement une petite parallélisation des appels teacher
- sur la stack locale Docker validee ici, `ollama` tourne sans GPU; les gros teachers locaux peuvent donc necessiter un `--timeout` plus grand ou un modele plus petit
- un teacher `local-hf` peut maintenant etre force sur une carte precise avec `--local-hf-device cuda:0`
- avec `--smoke` ou `--run-label`, dataset distille, merge et output training restent confines dans `finetune/runs/<label>_<domain>_<timestamp>/`
- ce run-dir contient aussi un `run.json` avec les etapes `distill`, `merge`, `train`, leurs commandes redactees et leurs statuts
- `steps.train.llmfit` recopie le noeud `llmfit` du `run.json` enfant produit par `run_local.py`
- `--teacher-only` force un run distillation-only et marque `train=skipped` dans le manifest

Scripts concernés:

- `finetune/distill_dataset.py`: génère le dataset distillé
- `finetune/distill_and_train.py`: enchaîne distillation, merge et training
- `scripts/distill_and_train.sh`: wrapper shell

## Batch multi-domaine

Pour enchaîner plusieurs domaines avec manifest et logs dédiés:

```bash
./scripts/parallel_domains_gpu_queue.sh freecad platformio \
  --max-source-samples 8 \
  --samples-per-source 1 \
  --student-max-samples 32 \
  --epochs 1 \
  --offline
```

Comportement du batch local valide sur cette machine:

- bootstrappe le seed dataset si `datasets/<domain>_chat.jsonl` manque mais qu un `build_<domain>_dataset.py` existe
- peut maintenant refresh explicitement les datasets avant batch/train:
  - `python finetune/dataset_refresh.py <domain>`
  - `run_local.py --refresh-dataset`
  - `batch_local.py --refresh-datasets`
- le refresh prefere `/ai/saisail/mascarade-datasets/<domain>_chat.jsonl` si ce repo local existe
- sinon il reconstruit depuis `finetune/datasets/build_<domain>_dataset.py`
- il ecrit aussi un brief de recherche web associe dans `finetune/research/`
- les anciens builders `finetune/build_components_dataset.py` et `finetune/build_freecad_dataset.py` sont retires du workflow; seuls `finetune/datasets/build_*` restent supportes
- le refresh dedupe maintenant le dataset final et trace `duplicates_removed`
- pre-valide le dataset source avant de lancer la moindre distillation; un dataset ShareGPT invalide casse le batch tout de suite
- applique aussi un quality gate automatique dataset; par defaut il bloque un dataset trop petit (`<4` rows), avec trop peu de prompts utilisateur uniques, ou avec des reponses anormalement verbeuses au `p95`
- logue explicitement les IDs source normalises quand des lignes arrivent sans `id`
- utilise par défaut `http://127.0.0.1:8100` avec `ollama` / `qwen2.5:14b`
- recharge `MASCARADE_API_KEY` depuis `.env` si elle n est pas deja exportee
- écrit un manifest et des logs par run dans `finetune/runs/`
- ajoute dans le manifest batch un resume court `source_rows / distilled_rows / merged_rows / failed_source_rows`
- ajoute aussi `duplicates_removed` quand la consolidation finale retire des rows en doublon
- overlap distill/train en mode `auto`: un domaine peut partir en training des que sa distillation est mergee
- avec un student CPU, ce mode reste actif meme pour `teacher-provider=local-hf`
- `--teacher-objective balanced` garde le meilleur compromis debit/qualite en local
- `--teacher-objective fast` est utile pour `teacher GPU -> student CPU`
- `--teacher-objective quality` est utile pour un run teacher-only ou une distillation plus lente mais plus ambitieuse
- pour un teacher `local-hf` sur GPU, utiliser `--local-hf-device cuda:0` ou exporter `MASCARADE_LOCAL_HF_DEVICE=cuda:0`
- teachers `local-hf` valides ici en vrai compute GPU: `Qwen/Qwen2.5-7B-Instruct` et `Qwen/Qwen3-4B-Instruct-2507`
- `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`, `Devstral-Small-2-24B-Instruct-2512` et `Mistral-Small-3.1-24B-Base-2503` restent exploites par defaut en `auto`/offload, pas en vrai compute GPU plein sur une RTX 4090 24 Go
- si `models_local/` n a plus assez d espace libre, le batch reroute automatiquement `train_output_dir` vers `/dev/shm/mascarade-train` et le manifeste garde `requested_train_output_dir` + `train_output_mode`
- avec `--max-parallel-gpu-trains 2`, le scheduler reste volontairement a `1` training tant que le teacher `ollama` distille encore sur une RTX 4090
- variables utiles pour le quality gate:
  - `MASCARADE_DATASET_QUALITY_MODE=off|warn|fail`
  - `MASCARADE_DATASET_QUALITY_MIN_ROWS=4`
  - `MASCARADE_DATASET_QUALITY_RECOMMENDED_ROWS=8`
  - `MASCARADE_DATASET_QUALITY_MIN_UNIQUE_USERS=4`
  - `MASCARADE_DATASET_QUALITY_MAX_ASSISTANT_P95=6000`
- variables utiles pour le refresh dataset:
  - `MASCARADE_FULL_DATASETS_ROOT=/ai/saisail/mascarade-datasets`
  - `MASCARADE_DATASET_RESEARCH_DIR=/ai/saisail/mascarade/finetune/research`
- une fois la file teacher vide, le scheduler decharge le modele `ollama` puis peut lancer `2` trainings students en parallele si la VRAM libre le permet
- le mode `--no-overlap-teacher-train` est maintenant une vraie barriere: un train pret bloque tout nouveau distill tant que la lane training GPU n est pas vide
- `gpu_job_vram_mb` peut maintenant etre laisse a `0` pour utiliser une estimation auto plus prudente
- `--teacher-only` ou `--skip-train` permettent un batch distill-only multi-domaine sans lancer `run_local.py`
- le choix du student suit maintenant cet ordre: `--student-model` explicite, puis `finetune/selected_model.json`, puis fallback repo
- le manifest batch expose un noeud racine `llmfit` pour le student courant
- chaque domaine recopie ensuite le `llmfit` du child `run.json` sous `domains.<domain>.train.llmfit`
- un training GPU refuse par `llmfit` est marque `train.status=blocked` plutot qu un simple `failed`

Refresh canonique + brief de recherche web:

```bash
python finetune/dataset_refresh.py stm32 platformio components --with-hf
python finetune/run_local.py stm32 --refresh-dataset --refresh-with-hf --device gpu
python finetune/batch_local.py stm32 spice pio --refresh-datasets --refresh-with-hf
```

Commande operateur canonique pour reprendre un batch:

```bash
python finetune/batch_status.py finetune/runs/<run_label>_<timestamp>/
python finetune/batch_local.py --resume finetune/runs/<run_label>_<timestamp>/

# Teacher rapide en vrai GPU + student CPU
python finetune/batch_local.py stm32 embedded \
  --teacher-objective fast \
  --device cpu \
  --max-source-samples 32 \
  --samples-per-source 2

# Teacher lourd offload prioritaire
python finetune/batch_local.py stm32 embedded \
  --teacher-objective quality \
  --teacher-only
```

Comportement de `--resume`:

- un domaine avec `distill=completed` et `train=pending` repart directement en training
- un domaine avec `distill=completed` et `train=completed` est saute
- un domaine `failed` reste visible dans le manifest; la reprise ne le marque pas artificiellement comme vert
- la reprise conserve le `student_model` deja fige dans le manifest, meme si `selected_model.json` a change depuis

Benchmark `gpu_slots` sur des datasets deja merges:

```bash
./scripts/benchmark_gpu_slots.sh \
  --source-manifest finetune/runs/sessions-4090-parallel-750x2_20260307_040828/manifest.json \
  --domains stm32,spice,kicad,platformio \
  --slots 1,2 \
  --label qwen4b-slots-compare \
  --offline
```

Resultat de reference sur cette machine:

- `Qwen/Qwen3-4B-Instruct-2507 @ seq_len=1024`
- `slots=1`: `78.01s`, pic VRAM `9532 MiB`
- `slots=2`: `42.01s`, pic VRAM `17119 MiB`
- speedup observe: `1.857x`

Profils machine a distinguer:

- le profil operateur est maintenant derive du materiel detecte
- `gpu_24gb_plus` valide ici:
  - `2` slots students sont supportes en training-only pour `Qwen/Qwen3-4B-Instruct-2507 @1024`
  - garder `1` slot tant qu un teacher GPU actif distille encore
- classes GPU plus contraintes:
  - rester conservateur a `1` slot tant qu aucun benchmark local comparable n a ete refait

## Matrice de scénarios teacher/student

Pour preparer ou executer plusieurs scénarios Qwen / Mistral / DeepSeek avec des passes
fixes `1 -> 2 -> 3`:

```bash
# Prepare seulement les manifests et les commandes
./scripts/teacher_student_scenarios.sh \
  --scenario-group all \
  --pass all \
  --prepare-only

# Executer seulement les scénarios DeepSeek, passe 1
./scripts/teacher_student_scenarios.sh \
  --scenario-group deepseek \
  --pass 1 \
  --offline

# Teacher auto rapide + student CPU
./scripts/teacher_student_scenarios.sh \
  --scenario auto_teacher_fast_to_tinyllama_cpu \
  --pass 1 \
  --offline

# Teacher auto quality en teacher-only
./scripts/teacher_student_scenarios.sh \
  --scenario auto_teacher_quality_teacher_only \
  --pass 1 \
  --offline

# Executer un teacher local GPU valide ici + student CPU
./scripts/teacher_student_scenarios.sh \
  --scenario qwen25_7b_instruct_to_tinyllama_cpu \
  --pass 1 \
  --offline
```

Comportement:

- un manifest parent `matrix.json` est ecrit sous `finetune/runs/<label>_<timestamp>/`
- chaque job de scenario appelle `finetune/batch_local.py` avec son propre `run-label`
- les scenarios sont groupes par famille `auto`, `qwen`, `mistral`, `deepseek`
- les scenarios `auto_teacher_*` laissent `batch_local.py` choisir le teacher selon `--teacher-objective`
- les scenarios CPU et GPU reutilisent le meme batch multi-domaine; les scenarios teacher-only passent par `--teacher-only`
- si le repo filesystem est plein, les outputs de training des scenarios partent automatiquement sous `/dev/shm/mascarade-train`
- les scenarios `qwen25_7b_instruct_to_tinyllama_cpu` et `qwen3_4b_instruct_2507_to_tinyllama_cpu` ciblent un teacher `local-hf` force sur `cuda:0`
- les scenarios `qwen35` / `devstral 24B` / `mistral 24B` / `deepseek coder lite` portent maintenant explicitement `--local-hf-device auto`
- les scenarios DeepSeek `coder` restent limites aux domaines code/embedded dans cette premiere version
- chaque job de `matrix.json` contient aussi un noeud `llmfit` calcule des la phase `--prepare-only`
- `matrix.json` maintient `summary.llmfit` pour compter rapidement les jobs `validated`, `warning`, `rejected` ou `unavailable`
- apres execution, le job recopie aussi le `llmfit` du child batch manifest et le resume des statuts de train par domaine
- un job GPU avec `llmfit.status=rejected` est marque `blocked` et n est pas lance

## Nettoyage des artifacts

Pour purger proprement les sorties de smoke test et les logs:

```bash
./scripts/cleanup_finetune_artifacts.sh --smoke --logs --distilled --dry-run
./scripts/cleanup_finetune_artifacts.sh --smoke --logs --distilled --yes
./scripts/cleanup_finetune_artifacts.sh --label smoke2 --yes
```

Pour supprimer un run temporaire nomme, utiliser `--label`. Pour un legacy output explicite hors run-dir, ajouter `--path`:

```bash
./scripts/cleanup_finetune_artifacts.sh \
  --smoke \
  --logs \
  --distilled \
  --path finetune/models_cpu/embedded \
  --yes
```

## Bootstrap de l'environnement

Le pipeline local attend un environnement dedie `venv_tuning`. Le bootstrap
installe `torch` depuis l'index PyTorch approprie puis les dependances du
pipeline:

```bash
# RTX 4090 / drivers CUDA recents
TORCH_CHANNEL=cu124 ./scripts/bootstrap_finetune_env.sh

# Anciennes cartes ou stack CUDA 11.8
TORCH_CHANNEL=cu118 ./scripts/bootstrap_finetune_env.sh

# CPU only
TORCH_CHANNEL=cpu ./scripts/bootstrap_finetune_env.sh
```

Pour les modeles `Qwen3.5`, utiliser la lane `transformers main`:

```bash
TRANSFORMERS_CHANNEL=main ./scripts/bootstrap_finetune_env.sh
```

## Architecture

```
Machine locale                    Google Colab (T4 gratuit)
    │                                    │
    │ 1. python datasets/build_*.py      │
    │    → datasets/*_chat.jsonl         │
    │                                    │
    │ 2. huggingface-cli upload           │
    │         ──────────────────────>    │
    │                                    │ 3. Ouvrir notebooks/finetune_*.ipynb
    │                                    │    Fine-tune Qwen2.5-Coder-7B (QLoRA)
    │                                    │    Export GGUF → HF Hub
    │         <──────────────────────    │
    │                                    │
    │ 4. ./deploy_model.sh <domain>      │
    │    → ollama create mascarade-*     │
    │                                    │
    │ 5. Modèle dispo dans Mascarade     │
    │    via OllamaProvider              │
```

## Domaines

| Domaine | Skills couverts | Dataset | Notebook |
|---------|----------------|---------|----------|
| **stm32** | stm32, stm32-asm, microcontroller-firmware | `stm32_chat.jsonl` | `finetune_stm32.ipynb` |
| **spice** | spice, spice-advanced-models, convergence-debug | `spice_chat.jsonl` | `finetune_spice.ipynb` |
| **iot** | mqtt-iot, esp-idf, rtos, domotique | `iot_chat.jsonl` | `finetune_iot.ipynb` |
| **power** | power-electronics, motor-control | `power_chat.jsonl` | `finetune_power.ipynb` |
| **dsp** | dsp-signal-processing | `dsp_chat.jsonl` | `finetune_dsp.ipynb` |
| **emc** | emc-emi, esd-protection, radio-rf | `emc_chat.jsonl` | `finetune_emc.ipynb` |
| **kicad** | pcb-routing-kicad, kicad, kicad-ia, pcb-design, IPC | `kicad_chat.jsonl` | `finetune_kicad.ipynb` |
| **components** | datasheet-reading, sourcing, alternates, bom-optimization, altium, easyeda | `components_chat.jsonl` | n/a |

## Quick Start Colab / Hub

### 1. Préparer le dataset

```bash
cd finetune

# Générer les seeds (20-30 exemples de haute qualité par domaine)
python datasets/build_stm32_dataset.py
python datasets/build_spice_dataset.py
python datasets/build_iot_dataset.py
python datasets/build_power_dataset.py
python datasets/build_dsp_dataset.py
python datasets/build_emc_dataset.py
python datasets/build_kicad_dataset.py
python datasets/build_components_dataset.py

# Inclure les datasets HuggingFace (tous les domaines supportés)
python datasets/build_stm32_dataset.py --with-hf --max-samples 2000
python datasets/build_spice_dataset.py --with-hf --max-samples 1000
python datasets/build_iot_dataset.py --with-hf --max-samples 2000
python datasets/build_power_dataset.py --with-hf --max-samples 2000
python datasets/build_dsp_dataset.py --with-hf --max-samples 2000
python datasets/build_emc_dataset.py --with-hf --max-samples 2000
python datasets/build_kicad_dataset.py --with-hf --max-samples 2000
python datasets/build_components_dataset.py --with-hf --max-samples 2000
```

### Sources HuggingFace par domaine

| Domaine | Datasets HF | Exemples estimés |
|---------|------------|-----------------|
| STM32 | `MuratKomurcu/stm32-hal-dataset` | ~2000 |
| SPICE | `STEM-AI-mtl/Electrical-engineering` (filtré) | ~500 |
| IoT | `gouthamsk/esp_idf_code` (13.7k), `acon96/Home-Assistant-Requests` (35.8k), `gavmac00/arduino-docs` (14.3k), `bshada/arduino.stackexchange.com` | ~5000+ |
| Power | `ksabeh/electronics-dataset` (128k filtré), `bshada/electronics.stackexchange.com` (filtré), `nick007x/eevblog-posts` (200k filtré) | ~2000+ |
| DSP | `bshada/electronics.stackexchange.com` (filtré), `common-pile/stackexchange` (DSP), `STEM-AI-mtl/Electrical-engineering` (filtré) | ~1000+ |
| EMC/RF | `bshada/electronics.stackexchange.com` (filtré), `STEM-AI-mtl/Electrical-engineering` (filtré), `nick007x/eevblog-posts` (filtré) | ~1000+ |
| KiCad/PCB | `STEM-AI-mtl/Electrical-engineering` (25% KiCad), `bshada/electronics.stackexchange.com` (filtré), `ksabeh/electronics-dataset` (filtré) | ~1500+ |
| Components | `bshada/electronics.stackexchange.com`, `STEM-AI-mtl/Electrical-engineering`, `nick007x/eevblog-posts` (filtres composants/datasheets/sourcing) + briefs web/distributeurs (`Mouser`, `Farnell`, `element14`, `LCSC`, `Octopart`, `SnapEDA`, `Ultra Librarian`) | ~25+ au smoke |

### 2. Enrichir le dataset (optionnel, au-delà de --with-hf)

Les datasets HF + seeds couvrent la majorité des cas. Pour aller plus loin :

- **Synthétique** : utiliser Claude/GPT-4 pour générer plus d'exemples dans le même format JSONL
- **Extraction** : extraire Q&A depuis vos projets, Stack Overflow, datasheets
- **Documentation** : convertir les appnotes TI/ST/Infineon en paires Q&A

Format attendu (ShareGPT) :
```json
{"conversations": [
  {"from": "system", "value": "You are an expert..."},
  {"from": "human", "value": "Question technique"},
  {"from": "gpt", "value": "Réponse détaillée avec code"}
]}
```

### 3. Upload sur HuggingFace

```bash
pip install huggingface_hub[cli]
huggingface-cli login

# Preparer un package dataset-ready
python prepare_hf_dataset.py components --username YOUR_USERNAME

# Puis uploader le package prepare
./upload_datasets_hf.sh
```

Le packaging canonical ecrit maintenant:

- `finetune/hf_datasets/<domain>/<domain>_chat.jsonl`
- `finetune/hf_datasets/<domain>/README.md`
- `finetune/hf_datasets/<domain>/metadata.json`

Le packaging HF dedupe aussi les rows finales et ecrit:

- `duplicates_removed_during_packaging` dans `metadata.json`

Le domaine `components` est dataset-ready pour HF, mais la promotion live de `mascarade-components`
reste derriere une revue manuelle.

Alias de revue courant:

- `mascarade-components-review`

Commandes:

```bash
python finetune/promotion_utils.py status components
python finetune/promotion_utils.py approve components
```

### 4. Fine-tuner sur Google Colab

1. Ouvrir le notebook correspondant dans Google Colab
2. Sélectionner Runtime → Change runtime type → **T4 GPU**
3. Remplacer `YOUR_USERNAME` par votre username HuggingFace
4. Exécuter toutes les cellules (~30-60 min)
5. Le GGUF est pushé automatiquement sur votre HF Hub

### 5. Déployer localement

```bash
./deploy_model.sh stm32 YOUR_USERNAME/mascarade-stm32-q4km
```

Le modèle est maintenant disponible dans Ollama et accessible via le provider Mascarade.

## Détails techniques

### Modèle de base
- **Qwen2.5-Coder-7B-Instruct** via Unsloth (4-bit QLoRA)
- LoRA rank: 16, alpha: 16
- Targets: q/k/v/o/gate/up/down projections

### Hyperparamètres d'entraînement
- Epochs: 3
- Learning rate: 2e-4
- Batch size: 2 (gradient accumulation: 4)
- Max sequence length: 2048
- Optimizer: AdamW 8-bit

### Export
- Quantization: Q4_K_M (bon compromis qualité/taille)
- Taille finale: ~4.3 GB par modèle
- Format: GGUF (compatible Ollama, llama.cpp)

## Structure

```
finetune/
├── README.md                  # Ce fichier
├── deploy_model.sh            # Script de déploiement
├── prepare_hf_dataset.py      # Prepare README + metadata + JSONL pour HF
├── upload_datasets_hf.sh      # Upload dataset packages vers HF
├── datasets/
│   ├── build_stm32_dataset.py # Génère stm32_chat.jsonl
│   ├── build_spice_dataset.py # Génère spice_chat.jsonl
│   ├── build_iot_dataset.py   # Génère iot_chat.jsonl
│   ├── build_power_dataset.py # Génère power_chat.jsonl
│   ├── build_dsp_dataset.py   # Génère dsp_chat.jsonl
│   ├── build_emc_dataset.py   # Génère emc_chat.jsonl
│   ├── build_components_dataset.py # Génère components_chat.jsonl
│   └── README.md              # Recap sources/licences/dataset folds
├── notebooks/
│   ├── finetune_stm32.ipynb   # Colab notebook STM32
│   ├── finetune_spice.ipynb   # Colab notebook SPICE
│   ├── finetune_iot.ipynb     # Colab notebook IoT
│   ├── finetune_power.ipynb   # Colab notebook Power
│   ├── finetune_dsp.ipynb     # Colab notebook DSP
│   └── finetune_emc.ipynb     # Colab notebook EMC/RF
└── modelfiles/
    ├── Modelfile.stm32        # Ollama Modelfile STM32
    ├── Modelfile.spice        # Ollama Modelfile SPICE
    ├── Modelfile.iot          # Ollama Modelfile IoT
    ├── Modelfile.power        # Ollama Modelfile Power
    ├── Modelfile.dsp          # Ollama Modelfile DSP
    ├── Modelfile.emc          # Ollama Modelfile EMC/RF
    └── Modelfile.components   # Ollama Modelfile Components
```
### Live web verification

- Dataset source registries live in `finetune/research_sources/domains/*.json`.
- `./scripts/sync_research_sources.sh` now performs a live HTTP probe and writes `finetune/research_probes/*.json`.
- `python finetune/dataset_refresh.py ...` re-runs the domain probe when missing or stale before accepting the dataset research brief.
- `./scripts/download_latest_finetune_models.sh` probes the Hugging Face model API before `snapshot_download`.
- `./scripts/bench_watch_candidate.sh --execute` probes the Hugging Face model API before downloading the watch candidate.
