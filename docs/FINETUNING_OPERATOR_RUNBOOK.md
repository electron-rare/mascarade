# Finetuning Operator Runbook

Date de reference: 2026-03-09

Ce runbook fige la conduite operateur actuelle du pipeline local `mascarade`.
Il couvre le batch local, la reprise, le benchmark des slots GPU et la politique
teacher/student retenue sur la machine detectee.

## 0. Workflow global

Chaine operateur actuelle:

`Sources locales/web -> build domaine -> normalisation -> quality gate -> dedupe -> package HF -> consommation par distill/train -> sélection modèle -> lot utile -> benchmark candidat -> pipeline SFT/DPO -> promotion`

Vue courte:

1. Les datasets sont rafraichis depuis les sources locales et les enrichissements web.
2. Chaque domaine passe par build, normalisation, quality gate et dedupe.
3. Le refresh est maintenant bloque si la recherche web associee n expose pas de vraies racines de sources, queries et domaines de confiance.
4. Les datasets valides sont packagés pour HF puis exposés au pipeline local.
5. Le selector met a jour le `selected_model.json` et le `model_watch_report.json`.
6. L orchestrateur calcule le prochain lot utile puis benchmarke le prochain candidat pertinent.
7. Le pipeline principal enchaine SFT, rejection sampling, DPO, merge/deploy et promotion.

## 1. Pre-requis

- repo: `/ai/saisail/mascarade`
- venv: `venv_tuning`
- GPU CUDA utilisable si run GPU
- cache HF local disponible pour les modeles auto retenus

Bootstrap minimal:

```bash
cd /ai/saisail/mascarade
. ./scripts/llm_env.sh
TRANSFORMERS_CHANNEL=main ./scripts/bootstrap_finetune_env.sh
./scripts/download_latest_finetune_models.sh
```

Stockage canonique des modeles:

- racine unique: `/ai/llm`
- cache HF: `/ai/llm/huggingface/hub`
- caches locaux: `/ai/llm/models_cache`
- watch/bench: `/ai/llm/watch_models`
- Apple LLM: `/ai/llm/apple-llm`

## 2. Politique operateur actuelle

### Profil machine

- le profil operateur est derive du materiel detecte
- sur cette machine:
  - classe: `gpu_24gb_plus`
  - GPU: `NVIDIA GeForce RTX 4090`
  - VRAM: `24564 MiB`

### Student

- auto par defaut: `Qwen/Qwen3.5-9B-Base`
- student valide pour batch/training parallele ici: `Qwen/Qwen3-4B-Instruct-2507`

### Teacher

- teacher auto par defaut sur domaines code-heavy:
  - `mistralai/Devstral-Small-2-24B-Instruct-2512`
- domaines code-heavy retenus:
  - `stm32`
  - `embedded`
  - `platformio`
  - `iot`
  - `kicad`
  - `freecad`
- fallback stable:
  - `ollama/qwen2.5:14b`

### Teachers manuels seulement

- `mistralai/Mistral-Small-3.1-24B-Base-2503`
- raison:
  - charge correctement
  - ne tient pas encore le schema JSON du pipeline en mode auto

## 3. Commandes canoniques

### Lot suivant actuel

Ordre opérateur retenu maintenant:

```bash
cd /ai/saisail/mascarade
. ./scripts/llm_env.sh

# 1. recalculer le prochain lot utile, lancer les smokes utiles et ecrire un rapport
./scripts/next_finetune_lots.sh --continue-on-error

# 2. preparer le benchmark watch courant sans rien lancer de lourd
./scripts/bench_watch_candidate.sh

# 3. lancer le benchmark watch seulement quand la VRAM est libre
./scripts/bench_watch_candidate.sh --execute
```

Point d entree unique pour la session complete:

```bash
cd /ai/saisail/mascarade
./scripts/start_tuning_party.sh
```

Point d entree TUI:

```bash
cd /ai/saisail/mascarade
./scripts/tuning_party_tui.sh
./scripts/tuning_party_tui.sh --dashboard
```

Contrat d usage:

- `./scripts/tuning_party_tui.sh` = vraie interface TUI interactive a menus.
- `./scripts/tuning_party_tui.sh --dashboard` = dashboard live auto-refresh avec barres et extraits de logs.
- `./scripts/start_tuning_party.sh --verbose` = lancement direct avec affichage de progression, monitoring et extraits de logs, sans menu interactif.
- depuis la TUI, `Start session` lance maintenant la session en arriere-plan puis ouvre directement le dashboard live.
- depuis la TUI, `Restart clean` fait `stop all -> resume GPU status -> relance -> dashboard`.

Comportement par defaut:

1. lance `next_finetune_lots.sh --continue-on-error`
2. demarre `auto_chain_next_lots_loop.sh` en arriere-plan
3. lance `finetune/batch_full_pipeline.sh` au premier plan

Modes utiles:

```bash
./scripts/start_tuning_party.sh --prepare-only
./scripts/start_tuning_party.sh --watch-only
./scripts/start_tuning_party.sh --pipeline-only
./scripts/start_tuning_party.sh --pipeline-arg --skip-phase-a
./scripts/start_tuning_party.sh --verbose
```

Pilotage de session:

```bash
./scripts/status_tuning_party.sh
./scripts/status_tuning_party.sh --verbose
./scripts/stop_tuning_party.sh
./scripts/stop_tuning_party.sh --force
./scripts/stop_tuning_party.sh --all --force
```

Rapport genere par l orchestrateur:

- `finetune/runs/next-lots_<timestamp>/summary.json`
- rapport de reference valide au 9 mars 2026:
  - `finetune/runs/next-lots_20260309_063107/summary.json`
  - `watch_refresh=ok`
  - `watch_bench=ok`
  - `prune=ok`
  - `cad_smoke=ok`
  - `components_review=ok`

Etat courant connu au 9 mars 2026:

- stockage modele consolide sous `/ai/llm`
- cache home redirige vers `/ai/llm/huggingface/hub`
- candidat watch resolu par le dry-run courant:
  - `JetBrains/Mellum-4b-sft-all`
- benchmark reel deja tente sur un candidat local proche:
  - `JetBrains/Mellum-4b-base`
- verdict:
  - stockage OK
  - loader quantized OK apres correctif
  - echec final si une autre lane GPU lourde occupe deja la carte

Blocage operateur courant:

- tant que la lane `tuning-party-hf` tourne encore, `bench_watch_candidate.sh --execute`
  bloque maintenant en preflight au lieu de finir en `CUDA OOM`

Commande de controle simple:

```bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits
```

### Batch local auto

```bash
cd /ai/saisail/mascarade
./scripts/parallel_domains_gpu_queue.sh iot spice platformio --offline
```

Labels historiques encore acceptes par le CLI:

- `esp32` -> `iot`
- `pio` -> `platformio`

### Refresh / packaging `components`

```bash
cd /ai/saisail/mascarade
. venv_tuning/bin/activate
python finetune/dataset_refresh.py components --with-hf
python finetune/prepare_hf_dataset.py components --username YOUR_USERNAME
```

Points verifies automatiquement:

- quality gate dataset
- normalisation des IDs source si necessaire
- dedupe final du dataset refresh
- dedupe final du package HF
- rapport `duplicates_removed` dans le brief refresh et `metadata.json`

### Lots utiles automatiques

Dry-run du prochain lot utile:

```bash
cd /ai/saisail/mascarade
./scripts/next_finetune_lots.sh --continue-on-error
```

Rapport de reference valide:

- `finetune/runs/next-lots_20260309_063107/summary.json`
- `cad_smoke=ok` sur workspace tmpfs
- `kicad_mcp=unavailable` tant que `finetune/kicad_mcp_server/package.json` manque

Benchmark watch explicite:

```bash
cd /ai/saisail/mascarade
./scripts/bench_watch_candidate.sh
./scripts/bench_watch_candidate.sh --execute
```

Enchainement auto des lots utiles:

```bash
cd /ai/saisail/mascarade
./scripts/auto_chain_next_lots.sh
./scripts/auto_chain_next_lots.sh --plan-only
./scripts/auto_chain_next_lots.sh --execute
./scripts/auto_chain_next_lots.sh --execute --iterations 2 --continue-on-error
```

Lancement en continu (recommandé pour enchaîner les prochains lots dès que la VRAM se libère):

```bash
cd /ai/saisail/mascarade
./scripts/auto_chain_next_lots_loop.sh \
  --iterations 1 \
  --sleep-seconds 600 \
  --max-blocked-streak 12 \
  --max-sleep-seconds 1800 \
  --max-cycles 0 \
  --stop-on-no-candidate
```

Le wrapper relance le lot utile périodiquement et applique la règle:
- `blocked` répétés => retry avec backoff via `--sleep-seconds` / `--max-sleep-seconds`.
- échecs non-bloqués répétés => arrêt progressif via `--max-failed-streak`.
- seuil `--max-ok-cycles` pour arrêter après N cycles contenant un `ok`.
- `--stop-on-no-candidate` pour stopper proprement quand aucun candidat n'est disponible.
- le wrapper pilote lui-même `--report-dir` ; n'utilise pas `--report-dir` via `--pass-through-arg` (verrouillé dans le script).

Exemple de ré-essai quand une lane GPU longue occupe la 4090:

```bash
cd /ai/saisail/mascarade
./scripts/auto_chain_next_lots.sh --execute --iterations 1 --continue-on-error
```

La boucle live actuelle suit maintenant ce cas sans intervention manuelle:

- `finetune/runs/auto-next-lots-live_20260309_072329_cycle_1/manifest.json`
- candidat courant: `JetBrains/Mellum-4b-sft-all`
- etat: `status=blocked`, en attente de libération de la 4090 par `tuning-party-hf`

Interpretation des retours:

- `status=ok` => benchmark exécuté.
- `status=blocked` (`exit_code=2`) => précheck GPU bloquant (VRAM occupée ou `nvidia-smi` invalide).
- `status=failed` => erreur pipeline run_local.
- Les manifests complets sont disponibles dans `manifest.json` et `run_manifest.json`.

Le script produit automatiquement:

- `finetune/runs/<label>_<timestamp>/manifest.json`
- `finetune/runs/<label>_<timestamp>/run_manifest.json`
- `finetune/runs/<label>_<timestamp>/candidates.txt`
- `finetune/runs/<label>_<timestamp>/bench-<idx>-<safe>.log`
- `finetune/runs/<label>_<timestamp>/plan-summary.json`

Notes:

- le script benchmarke d abord le cache local `/ai/llm` avant tout download
- en mode `--execute`, il bloque maintenant en preflight si la VRAM libre est insuffisante
- `--force` existe, mais n est utile que si tu veux volontairement ignorer une contention GPU deja identifiee
- si un snapshot local complet existe deja dans `/ai/llm/watch_models` ou `/ai/llm/huggingface/hub`, il est reutilise tel quel

Consolidation des anciens caches/modeles vers `/ai/llm`:

```bash
cd /ai/saisail/mascarade
./scripts/migrate_models_to_llm.sh
./scripts/migrate_models_to_llm.sh --execute --cleanup --link-home-cache
```

### Promotion live d un modele valide

```bash
cd /ai/saisail/mascarade
. venv_tuning/bin/activate
python finetune/pipeline.py platformio --step deploy
```

Notes:

- le deploy Ollama choisit maintenant automatiquement `host` ou `container`
- sur cette machine, il part sur l Ollama hote parce que `mascarade-ollama` monte `/root/.ollama` en lecture seule
- si le filesystem du repo est plein, la promotion stage automatiquement sous `/dev/shm/mascarade-promotion`
- dans le meme cas, `run_local.py` et `batch_local.py` reroutent aussi les outputs de training sous `/dev/shm/mascarade-train` ou `MASCARADE_TRAIN_WORKDIR`
- aliases live actuellement valides:
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

### Revue manuelle `components`

Le domaine `components` ne remplace pas automatiquement l alias live.
Le pipeline le stage sous un alias de revue:

- alias de revue: `mascarade-components-review`
- alias live cible: `mascarade-components`

Statut / approbation:

```bash
cd /ai/saisail/mascarade
. venv_tuning/bin/activate
python finetune/promotion_utils.py status components
python finetune/promotion_utils.py approve components
```

Politique:

- `stage` construit `merge -> gguf -> deploy -> smoke`
- si le smoke passe, le registre passe en `pending_manual_review`
- seul `approve` remplace ensuite l alias live

### Reprendre un batch

```bash
cd /ai/saisail/mascarade
python finetune/batch_status.py finetune/runs/<run_label>_<timestamp>/
python finetune/batch_local.py --resume finetune/runs/<run_label>_<timestamp>/
```

### Batch court de validation

```bash
cd /ai/saisail/mascarade
. venv_tuning/bin/activate
python finetune/batch_local.py iot spice platformio \
  --run-label smoke-batch \
  --device gpu \
  --student-model Qwen/Qwen3-4B-Instruct-2507 \
  --max-source-samples 1 \
  --samples-per-source 1 \
  --max-parallel-distills 1 \
  --max-parallel-gpu-trains 1 \
  --student-max-samples 4 \
  --seq-len 256 \
  --epochs 1 \
  --tokenize-workers 1 \
  --offline \
  --max-tokens 96 \
  --json-retries 1 \
  --no-overlap-teacher-train
```

### Distillation seule sur `platformio`

```bash
cd /ai/saisail/mascarade
. venv_tuning/bin/activate
python finetune/distill_dataset.py platformio \
  --source-dataset finetune/datasets/platformio_chat.jsonl \
  --out .tmp/pio_smoke.jsonl \
  --report-path .tmp/pio_smoke.report.json \
  --failures-out .tmp/pio_smoke.failures.jsonl \
  --strategy routellm \
  --temperature 0.4 \
  --max-tokens 96 \
  --timeout 120 \
  --max-source-samples 1 \
  --samples-per-source 1 \
  --concurrency 1 \
  --json-retries 1 \
  --seed 42 \
  --sleep-ms 0 \
  --teacher-provider local-hf \
  --teacher-model mistralai/Devstral-Small-2-24B-Instruct-2512 \
  --verbose \
  --local-hf-device auto
```

### Validation post-training actuelle

Ce qui est valide aujourd hui dans la pipeline:

- le smoke de promotion live lance l alias Ollama via `finetune/promotion_utils.py`
  avec un prompt domaine-specifique (`SMOKE_PROMPTS`)
- ce smoke valide donc bien:
  - le `merge -> gguf -> deploy`
  - la disponibilite de l alias `mascarade-<domain>`
  - une reponse texte specialisee sur le domaine
- ce smoke ne valide pas encore un vrai workflow MCP/tooling type:
  - `pio run`
  - `kicad-cli` / DRC
  - `FreeCADCmd`
  - `OpenSCAD`

Ce qui est maintenant valide dans le lot operateur separe:

- `./scripts/cad_tool_smoke_tmpfs.sh`
  - workspace par defaut sous `/dev/shm/mascarade-cad-smoke/<label>_<timestamp>/`
  - `doctor=ok`
  - `kicad=ok`
  - `freecad=ok`
  - `platformio=ok`
  - `kicad_mcp=unavailable` si `finetune/kicad_mcp_server/package.json` manque
- `./scripts/next_finetune_lots.sh`
  - orchestre `watch-refresh`, `watch-bench`, `prune-unvalidated`, `cad-tool-smoke`, `components-review`
  - ecrit un rapport sous `finetune/runs/next-lots_<timestamp>/summary.json`

Etat exact des validateurs utilises aujourd hui dans le code:

- `stm32`, `embedded`:
  - compilation syntaxique C via `arm-none-eabi-gcc` ou `gcc`
- `spice`:
  - simulation batch `ngspice`
- `kicad`:
  - verification S-expression / contenu KiCad, pas de DRC complet automatique dans le smoke actuel
- `platformio`:
  - verification structurelle (`platformio.ini`, `setup/loop`, includes), pas encore de `pio run` automatique dans le smoke actuel
- `freecad`, `components`, `dsp`, `power`, `emc`, `iot`:
  - fallback `LLMJudgeValidator`, pas de validation outillee deterministe locale aujourd hui

Outillage dispo mais non branche automatiquement dans le smoke de promotion:

- `scripts/cad_stack.sh kicad-cli ...`
- `scripts/cad_stack.sh freecad-cmd ...`
- `scripts/cad_stack.sh pio ...`
- `scripts/cad_stack.sh mcp ...` pour le serveur MCP KiCad

Conclusion operateur:

- oui, il existe deja une couche de validation technique partielle
- non, la pipeline post-training ne fait pas encore un vrai test MCP outille
  dans le smoke de promotion
- oui, un smoke outille separe existe maintenant pour `platformio`, `kicad` et `freecad`
  via `scripts/cad_tool_smoke_tmpfs.sh`
- `OpenSCAD` reste hors couverture automatique sur cette stack
- `kicad_mcp` reste en statut `unavailable` tant que le serveur source local n est pas peuple

## 4. Politique de parallélisme GPU

- si un teacher GPU actif distille encore:
  - garder `1` slot student
- si la file teacher est vide:
  - `2` slots student autorises sur `gpu_24gb_plus` pour `Qwen/Qwen3-4B-Instruct-2507`
- `--no-overlap-teacher-train` est maintenant une vraie barriere:
  - un train pret bloque tout nouveau distill

### Benchmark de reference

Commande:

```bash
cd /ai/saisail/mascarade
./scripts/benchmark_gpu_slots.sh \
  --source-manifest finetune/runs/sessions-4090-parallel-750x2_20260307_040828/manifest.json \
  --domains stm32,spice,kicad,platformio \
  --slots 1,2 \
  --label qwen4b-slots-compare \
  --offline
```

Resultat de reference:

- `Qwen/Qwen3-4B-Instruct-2507 @ seq_len=1024`
- `slots=1`: `78.01s`, pic VRAM `9532 MiB`
- `slots=2`: `42.01s`, pic VRAM `17119 MiB`
- speedup observe: `1.857x`

## 5. Etats de succes a verifier

Dans le manifest batch:

- `distill.status=completed`
- `train.status=completed`
- `failed_source_rows=0` si le lot est propre
- `duplicates_removed=0` si la consolidation finale n a pas eu a purger de doublons

Pour un batch multi-domaine:

- `summary.distills_completed == summary.domains_total`
- `summary.trains_completed == summary.domains_total`
- `summary.duplicates_removed` doit rester lisible et explique toute purge finale

## 6. Decisions verrouillees

- `Devstral` est la voie auto de reference sur domaines code-heavy en `gpu_24gb_plus`
- `Mistral-Small-3.1-24B-Base-2503` reste `manual-only`
- `2` slots student sont valides ici en training-only, pas pendant une distillation GPU lourde
- le benchmark slots doit etre refait sur toute classe GPU plus contrainte avant de generaliser
- le deploy GGUF vers Ollama doit preferer l hote quand le conteneur partage un store modele read-only
- le deploy de promotion peut utiliser un scratch `/dev/shm` si le repo filesystem est sature
- les outputs de training ne vont pas toujours en tmpfs:
  - ils restent dans le chemin demande tant que l espace libre est suffisant
  - ils basculent vers `/dev/shm/mascarade-train` seulement si le repo n a plus assez de marge
- les fichiers de review/promotion peuvent aussi passer en tmpfs:
  - `/dev/shm/mascarade-promotion`
  - `/dev/shm/mascarade-review`
- aliases live actuellement publies et smoke valides: `mascarade-platformio`, `mascarade-stm32`, `mascarade-spice`, `mascarade-iot`, `mascarade-kicad`, `mascarade-freecad`, `mascarade-dsp`, `mascarade-embedded`, `mascarade-power`, `mascarade-emc`
- `mascarade-components-review` est review-ready au 9 mars 2026, pas encore promu live
- `mascarade-iot` est aussi valide via `POST /api/agents/send` avec `provider=ollama`
- `mascarade-kicad` est aussi valide via `POST /api/agents/send` avec `provider=ollama`
- `mascarade-freecad`, `mascarade-dsp` et `mascarade-embedded` sont aussi valides via `POST /api/agents/send` avec `provider=ollama`
- `mascarade-power` et `mascarade-emc` sont aussi valides via `POST /api/agents/send` avec `provider=ollama`

## 7. References

- doc pipeline: `finetune/README.md`
- cheatsheet: `docs/archive/finetuning/FINETUNING_CHEATSHEET_2026-03-06.md`
- shortlist modeles: `docs/archive/finetuning/FINETUNING_MODEL_SHORTLIST_2026-03-08.md`
- plan parallelisme 4090: `docs/FINETUNING_4090_PARALLEL_PLAN.md`
