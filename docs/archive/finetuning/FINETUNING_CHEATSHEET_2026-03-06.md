# Fine-Tuning Cheatsheet

Date de reference: 2026-03-06

Version courte du document complet:

- voir `docs/archive/finetuning/FINETUNING_ETAT_DE_L_ART_2026-03-06.md` pour le detail

## 1. Regle simple

Pour cette machine:

- ne vise pas un gros fine-tuning dense
- vise un petit student local
- utilise un gros teacher pour generer de bonnes donnees
- fais du SFT en LoRA/QLoRA

## 2. Quel chemin choisir

| Si ton besoin est... | Fais ca |
|---|---|
| format, style, procedure, ton | SFT |
| transferer la qualite d un gros modele vers un petit | distillation + SFT |
| choisir entre plusieurs bonnes ou mauvaises reponses | DPO / ORPO / KTO |
| optimiser une tache objectivement notee | GRPO / RFT |
| injecter beaucoup de savoir brut | continued pretraining |
| entrainer un gros modele serieusement | cloud / managed |

## 3. Ce qui est realiste ici

Machine actuelle:

- GPU RTX 4090
- environ 24 Go de VRAM

Donc:

- 1B a 4B: facile
- 7B dense en QLoRA 4-bit: oui, c est la bonne cible
- gros MoE / agentic coders recents: plutot pour inference, pas comme premier student local ici
- full fine-tuning dense: non, rester sur LoRA / QLoRA

## 4. Workflow recommande

1. definir un petit eval set
2. distiller avec un gros teacher
3. fusionner source + distillation
4. fine-tuner un petit student local
5. evaluer avant/apres

## 5. Commandes utiles

Check environnement:

```bash
./scripts/bootstrap_finetune_env.sh
source venv_tuning/bin/activate
python test_environment.py
```

Fine-tuning local simple:

```bash
python finetune/run_local.py stm32 --device auto --max-samples 128 --epochs 1
```

Build `llmfit` pour activer le preflight hardware dans le pipeline:

```bash
cd /ai/saisail/llmfit
cargo +stable build --release -p llmfit
```

Preset adapte a cette machine :

```bash
./scripts/finetune_host_gpu.sh stm32
```

Preset plus agressif pour `stm32` sur RTX 4090 :

```bash
./scripts/finetune_stm32_4090.sh
```

Preset plus agressif pour `platformio` sur RTX 4090 :

```bash
./scripts/finetune_platformio_4090.sh
```

Preset solo `Qwen3.5-9B-Base` sur RTX 4090 :

```bash
./scripts/finetune_qwen35_base_4090.sh
```

Telechargement cible des modeles recents retenus par la politique auto :

```bash
./scripts/download_latest_finetune_models.sh
```

Profil multi-run RTX 4090 :

```bash
./scripts/triple_train_4090.sh
./scripts/triple_train_4090_safe_max.sh
MODE=triple-mixed-1024 ./scripts/triple_train_4090.sh
MODE=triple-staggered-8b1024-4b768 ./scripts/triple_train_4090.sh
MODE=dual-8b-512 ./scripts/triple_train_4090.sh
```

Distillation seule:

```bash
python finetune/distill_dataset.py stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider ollama \
  --teacher-model qwen2.5:14b \
  --max-source-samples 32 \
  --samples-per-source 2
```

Pipeline complet teacher -> student:

```bash
./scripts/distill_and_train.sh stm32 \
  --api-url http://127.0.0.1:8100 \
  --teacher-provider ollama \
  --teacher-model qwen2.5:14b \
  --max-source-samples 32 \
  --samples-per-source 2 \
  --device gpu \
  --epochs 1
```

Reprise batch canonique:

```bash
python finetune/batch_status.py finetune/runs/<run_label>_<timestamp>/
python finetune/batch_local.py --resume finetune/runs/<run_label>_<timestamp>/
```

Refresh / packaging `components`:

```bash
python finetune/dataset_refresh.py components --with-hf
python finetune/prepare_hf_dataset.py components --username YOUR_USERNAME
python finetune/promotion_utils.py status components
```

Benchmark `gpu_slots` sur un run deja distille:

```bash
./scripts/benchmark_gpu_slots.sh \
  --source-manifest finetune/runs/sessions-4090-parallel-750x2_20260307_040828/manifest.json \
  --domains stm32,spice,kicad,platformio \
  --slots 1,2 \
  --label qwen4b-slots-compare \
  --offline
```

## 6. Reglage de depart recommande

Teacher:

- le `teacher` n est plus fige
- mode auto par defaut: `--teacher-objective balanced`
- `balanced`: `Qwen/Qwen2.5-7B-Instruct` puis `Qwen/Qwen3-4B-Instruct-2507`
- `quality`: `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` puis `Devstral 24B`, puis `Mistral 24B`
- `fast`: `Qwen/Qwen3-4B-Instruct-2507` puis `Qwen/Qwen2.5-7B-Instruct`
- fallback stable si rien ne passe: `ollama/qwen2.5:14b`
- les teachers `local-hf` lourds du mode `quality` partent en `local_hf_device=auto`, pas en `cuda:0` force
- pour de la vraie distillation GPU locale sur cette 4090, les teachers `local-hf` valides aujourd hui sont `Qwen/Qwen2.5-7B-Instruct` et `Qwen/Qwen3-4B-Instruct-2507`
- pour ces teachers, forcer `--local-hf-device cuda:0` ou exporter `MASCARADE_LOCAL_HF_DEVICE=cuda:0`
- `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`, `Devstral-Small-2-24B-Instruct-2512` et `Mistral-Small-3.1-24B-Base-2503` restent des teachers `auto`/offload utiles, mais pas des vrais teachers plein GPU sur une seule RTX 4090 24 Go

Student:

- recommande auto sur cette machine: `Qwen/Qwen3.5-9B-Base`
- recommande historique pour ce repo: `Qwen/Qwen2.5-Coder-7B-Instruct`
- alternative generaliste recente et plus legere: `Qwen/Qwen3-4B-Instruct-2507`
- alternative plus recente pour fine-tuning solo: `Qwen/Qwen3.5-9B-Base`
- ne pas prendre `Qwen3-Coder-Next` comme premier student local: c est un gros modele hybride/MoE surtout pense pour serving agentic
- ne pas prendre `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4` comme student local: teacher / inference only dans ce pipeline

Charge validee sur cette machine:

- `1 x Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=512`: valide
- `1 x Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=768`: valide
- `1 x Qwen/Qwen3-8B + 2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=1024`: valide, mais avec peu de marge VRAM
- `1 x Qwen/Qwen3-8B` en `seq-len=1024` + `2 x Qwen/Qwen3-4B-Instruct-2507` en `seq-len=768`: valide, avec une marge plus confortable
- `2 x Qwen/Qwen3-8B` en `seq-len=512`: non stable, un des deux run finit en `CUDA OOM`
- preset `safe-max` courant: `./scripts/triple_train_4090_safe_max.sh` sur `seq-len=768`
- `run_local.py` peut maintenant ecrire un `llmfit_plan.json` par run pour garder une trace du sizing inference utilise comme garde-fou avant training
- `run_local.py` ecrit aussi un `run.json` quand `--output-dir` est force, avec un noeud racine `llmfit`
- `batch_local.py` remonte ce `llmfit` enfant dans le manifest batch sous `domains.<domain>.train.llmfit`
- `batch_scenarios.py` expose un `llmfit` par job dans `matrix.json` des la phase `--prepare-only`
- si `llmfit` n est pas present, le pipeline continue sans bloquer et logue un warning
- `batch_local.py` peut maintenant monter a `2` students, mais seulement en fin de batch quand la file teacher est vide
- avec un teacher `ollama` lourd, le scheduler garde `1` seul student pendant les distills puis decharge le modele teacher pour recuperer la VRAM avant d ouvrir le deuxieme slot
- benchmark training-only valide au 8 mars 2026 sur `gpu_24gb_plus`:
  - `Qwen/Qwen3-4B-Instruct-2507 @ seq-len=1024`
  - `slots=1`: `78.01s`, pic VRAM `9532 MiB`
  - `slots=2`: `42.01s`, pic VRAM `17119 MiB`
  - speedup observe: `1.857x`
- `OLLAMA_API_URL` permet de cibler un endpoint Ollama different pour ce dechargement automatique
- `batch_local.py` choisit maintenant le student selon `--student-model` explicite, puis `finetune/selected_model.json`, puis le fallback repo
- si `selected_model.json` est absent, `batch_local.py` et `run_local.py` choisissent maintenant le student selon le materiel detecte
- `model_selector.py` garde maintenant son cache et `selected_model.json` dans un state runtime dedie (`/tmp/mascarade-finetune-state` en sandbox, `/dev/shm/mascarade-finetune-state` hors sandbox) pour ne pas casser quand le repo FS est plein
- `model_selector.py --watch --refresh --task code` ajoute une veille web recente sur les sorties des auteurs de confiance et ecrit `model_watch_report.json` dans ce meme state runtime
- `run_local.py` et `batch_local.py` reutilisent aussi ce workflow: sans `--model` / `--student-model` explicite et hors `--offline`, ils rafraichissent la veille/selection quand le cache TTL est stale puis tracent le `model_watch_report.json` retenu
- benchmark selector vs manuel valide au 8 mars 2026:
  - artefact: `finetune/runs/model-selector-benchmark-live_20260308_213050/summary.json`
  - verdict: alignement sur `Qwen/Qwen3.5-9B-Base`
- `batch_local.py` choisit maintenant aussi automatiquement le `teacher`, `gpu_slots`, `seq_len` et `student_max_samples` quand ces flags ne sont pas forces
- `--teacher-objective balanced` est le defaut pratique
- `--teacher-objective fast` privilegie un teacher `local-hf` 4B/7B en vrai GPU
- `--teacher-objective quality` privilegie un gros teacher `local-hf` 35B/24B en offload
- sur des domaines tres code-heavy, `Devstral 24B` peut remonter plus haut dans l ordre auto
- la politique hardware-adaptive garde maintenant le chemin GPU si le GPU NVIDIA est detecte/profilé, meme quand `torch.cuda.is_available()` est bruité dans certains shells; le trainer garde ses propres garde-fous runtime
- `--auto-promote` remplace l alias live uniquement quand `merge -> gguf -> deploy -> smoke` passent tous
- le deploy Ollama choisit automatiquement `host` ou `container`; sur cette machine, le chemin live valide utilise l Ollama hote car le conteneur a un store read-only
- si le filesystem du repo est sature, la promotion stage automatiquement sous `/dev/shm/mascarade-promotion`
- si le filesystem du repo est sature, `run_local.py` et `batch_local.py` reroutent maintenant aussi les outputs de training sous `/dev/shm/mascarade-train` ou `MASCARADE_TRAIN_WORKDIR`
- nuance: ces outputs ne vont pas toujours en tmpfs; le basculement vers `/dev/shm` se fait seulement quand le repo FS n a plus assez d espace
- le smoke post-promotion actuel valide l alias Ollama et une reponse texte domaine-specifique
- il ne couvre pas encore automatiquement un vrai workflow outille/MCP `pio` / `kicad-cli` / `FreeCADCmd` / `OpenSCAD`
- l outillage operateur existe maintenant via:
  - `scripts/cad_tool_smoke_tmpfs.sh`
  - `scripts/next_finetune_lots.sh --continue-on-error`
- couverture outillee validee au 9 mars 2026:
  - `doctor=ok`
  - `kicad=ok`
  - `freecad=ok`
  - `platformio=ok`
  - `kicad_mcp=unavailable` tant que `finetune/kicad_mcp_server/package.json` manque
  - rapport vert de reference: `finetune/runs/next-lots_20260309_063107/summary.json`
- `OpenSCAD` reste hors couverture automatique sur cette stack
- quality gate dataset actif par defaut:
  - bloque les datasets `<4` rows, avec trop peu de prompts utilisateur uniques, ou avec des reponses trop verbeuses au `p95`
  - variables: `MASCARADE_DATASET_QUALITY_MODE`, `MASCARADE_DATASET_QUALITY_MIN_ROWS`, `MASCARADE_DATASET_QUALITY_MIN_UNIQUE_USERS`, `MASCARADE_DATASET_QUALITY_MAX_ASSISTANT_P95`
- refresh dataset canonique disponible:
  - `python finetune/dataset_refresh.py stm32 platformio components --with-hf`
  - `run_local.py --refresh-dataset` et `batch_local.py --refresh-datasets` le branchent directement dans le workflow
  - le refresh prefere `mascarade-datasets/` si present, sinon `finetune/datasets/build_*`
  - un brief de recherche web associe est ecrit dans `finetune/research/`
  - les anciens builders `finetune/build_components_dataset.py` et `finetune/build_freecad_dataset.py` sont retires
  - le refresh dedupe maintenant le dataset final et trace `duplicates_removed`
- la consolidation distill/train et le packaging HF dedupent aussi les rows finales et tracent `duplicates_removed`
- le profil operateur n est plus fige sur P2000; il est derive de la machine presente
- alias live valide actuel:
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
  - registre: `finetune/models_local/promotion_registry.json`
  - `mascarade-components-review` est review-ready, la promotion live `mascarade-components` reste sous revue manuelle
  - `mascarade-iot` est aussi valide via `POST /api/agents/send`
  - `mascarade-kicad` est aussi valide via `POST /api/agents/send`
  - `mascarade-freecad`, `mascarade-dsp` et `mascarade-embedded` sont aussi valides via `POST /api/agents/send`
  - `mascarade-power` et `mascarade-emc` sont aussi valides via `POST /api/agents/send`

Hyperparametres de depart:

- `max-source-samples=32`
- `samples-per-source=2`
- `epochs=1`
- `seq-len=1024`

Puis monter doucement:

- `max-source-samples=64`
- `epochs=2`

Bootstrap `Qwen3.5`:

```bash
TRANSFORMERS_CHANNEL=main ./scripts/bootstrap_finetune_env.sh
```

Preset `stm32` RTX 4090 deja prepare dans le repo:

- `max-source-samples=128`
- `samples-per-source=2`
- `student-max-samples=384`
- `seq-len=1536`
- `epochs=2`

## 7. Ce qu il ne faut pas faire trop tot

- lancer DPO avant un bon SFT
- lancer du RL sans grader robuste
- viser un gros dense ou un MoE sans avoir valide le baseline 7B dense
- remplacer un eval set par une impression subjective
- empiler des methodes avant d avoir valide le baseline

## 8. Ordre de priorite

Avant de complexifier:

1. meilleur eval set
2. meilleur dataset
3. meilleure distillation
4. meilleur SFT
5. ensuite seulement preference tuning ou RL

## 9. Lecture suivante

- recap complet: `docs/archive/finetuning/FINETUNING_ETAT_DE_L_ART_2026-03-06.md`
- doc pipeline local: `finetune/README.md`
- plan 4090 / parallélisme: `docs/FINETUNING_4090_PARALLEL_PLAN.md`
