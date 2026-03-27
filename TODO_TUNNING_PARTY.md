# TODO - Fine-Tuning Local

Etat de reference au 6 mars 2026.
Mis a jour apres audit croise code/docs le 7 mars 2026.

## 1. Ce qui est deja en place

- [x] Pipeline local `distill -> merge -> train`
- [x] Distillation teacher via Mascarade local (`127.0.0.1:3100` / `127.0.0.1:8100`)
- [x] Support CPU et GPU local
- [x] Defaut GPU / student principal derive du hardware detecte
- [x] Fallback CPU canonique = `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- [x] Smoke tests reels distillation valides sur `iot` (label historique `esp32`), `spice`, `platformio` (`pio`)
- [x] Queue GPU et garde-fous VRAM dans `finetune/batch_local.py`
- [x] Scripts shell de lancement et de debug
- [x] Racine canonique des modeles locale fixee a `/ai/llm`
- [x] `finetune/model_selector.py` disponible comme outil local benchmarke

## 2. Implemente depuis le dernier TODO (verifie par audit)

- [x] `batch_status.py` distingue correctement `distill` et `train` par domaine
- [x] `--resume` fonctionne: `load_resume_manifest()`, skip des domaines completed
- [x] `selected_model.json` lu par `run_local.py` au boot via `resolve_model()`
- [x] Export GGUF complet dans `pipeline.py` (`step_gguf()`): q4_k_m, q4_k_s, q5_k_m, q8_0
- [x] Deploy GGUF vers Ollama dans `pipeline.py` (`step_deploy()`): docker cp/exec + test inference
- [x] Unload Ollama model (keep_alive=0) avant training parallele GPU
- [x] Scheduler batch `--no-overlap-teacher-train` corrige: un train pret bloque maintenant tout nouveau distill GPU
- [x] Auto-selection teacher orientee materiel + domaine: `Devstral` priorise sur domaines code-heavy en `gpu_24gb_plus`
- [x] Mode `--teacher-objective fast|balanced|quality` branche dans `batch_local.py` et `distill_and_train.py`
- [x] Scenarios `auto_teacher_*` ajoutes dans `batch_scenarios.py` / `scenario_matrix.py`
- [x] `Devstral` valide comme teacher operateur par defaut sur `iot` (label historique `esp32`), `spice` et `platformio` (`pio`) en profil `gpu_24gb_plus`
- [x] `mistralai/Mistral-Small-3.1-24B-Base-2503` declassé du mode auto: conserve en reference manuelle / experimentation
- [x] Reroutage automatique des outputs de training vers `/dev/shm/mascarade-train` quand le filesystem du repo est plein
- [x] CPU trainer allégé: plus de checkpoints intermediaires par defaut, seul l adapter final est conserve
- [x] Workflow de selection auto enrichi avec une veille web recente sur les auteurs/modeles adaptes (`model_selector.py --watch`, puis refresh auto dans `run_local.py` / `batch_local.py` hors `--offline`)
- [x] Scripts d enchainement automatique des prochains lots utiles
  - `scripts/next_finetune_lots.sh`
  - `scripts/bench_watch_candidate.sh`
  - `scripts/auto_chain_next_lots.sh`
  - `scripts/auto_chain_next_lots_loop.sh` (chainage continu + retry backoff)
  - `scripts/migrate_models_to_llm.sh`
  - Robustesse récente: `bench_watch_candidate` classe proprement les préchecks bloquants GPU en `status=blocked` (RC=2) et parse de façon tolérante les payloads `nvidia-smi` non valides.
  - Validation live au 9 mars 2026:
    - `finetune/runs/next-lots_20260309_063107/summary.json`
    - `watch_refresh=ok`
    - `watch_bench=ok` avec plan dry-run sur `JetBrains/Mellum-4b-sft-all`
    - `prune=ok` (0 cache non valide a supprimer dans l etat courant)
    - `cad_smoke=ok` via workspace tmpfs `/dev/shm/mascarade-cad-smoke/...`
    - `components_review=ok`
  - Couverture outillage validee par `scripts/cad_tool_smoke_tmpfs.sh`:
    - `doctor=ok`
    - `kicad=ok`
    - `freecad=ok`
    - `platformio=ok`
    - `kicad_mcp=unavailable` tant que `finetune/kicad_mcp_server/package.json` reste absent

Politique active de stabilisation machine:
- [x] Stopper les lanes CPU paralleles en cours quand la RAM/swap passe sous pression
- [x] Repasser `finetune/train_parallel.sh` en serie par defaut sur cette machine
- [x] Garder tout override `--parallel > 1` derriere `MASCARADE_ALLOW_PARALLEL_CPU=1`

## 3. Backlog reel

### Priorite immediate
- [x] Valider un run batch complet `iot spice platformio` (labels historiques `esp32 spice pio`) jusqu'a `train=completed`
- [x] Ecrire la commande standard de reprise `--resume` dans la doc operateur
- [x] Geler un runbook operateur dedie: `docs/FINETUNING_OPERATOR_RUNBOOK.md`
- [x] Declasser officiellement `mistralai/Mistral-Small-3.1-24B-Base-2503` en reference manuelle tant qu il ne tient pas le schema JSON

### Priorite suivante
- [x] Comparer `max_parallel_gpu_trains=1` vs `2` sur le profil `gpu_24gb_plus` present
- [x] Mesurer temps total, VRAM libre et stabilite
- [x] Valider `2` slots GPU sur RTX 4090 pour `Qwen/Qwen3-4B-Instruct-2507` en training-only a `seq_len=1024`
- [ ] Refaire ce benchmark sur une classe GPU plus contrainte si elle redevient disponible

### Stabilisation dataset
- [x] Ajouter un garde-fou de prevalidation source avant lancement batch
- [x] Rendre explicite dans les logs quand la normalisation corrige les IDs manquants
- [x] Ajouter un rapport court sur `source_rows`, `distilled_rows`, `merged_rows`
- [x] Ajouter un quality gate automatique dataset dans `run_local.py`, `batch_local.py`, `distill_dataset.py`, `distill_and_train.py`, `train_local.py`, `train_cpu.py` et `pipeline.py`
- [x] Ajouter un workflow de refresh dataset avec recherche web associee
  - `finetune/dataset_refresh.py`
  - `run_local.py --refresh-dataset`
  - `batch_local.py --refresh-datasets`
  - priorite au repo local `mascarade-datasets/`, sinon builders canoniques `finetune/datasets/build_*`
  - briefs de recherche web sous `finetune/research/`
- [x] Canoniser `components` dans le workflow
  - domaine supporte dans `run_local.py`, `batch_local.py`, `distill_dataset.py`, `pipeline.py`, `train_local.py`, `train_cpu.py`
  - builder canonique: `finetune/datasets/build_components_dataset.py`
  - coverage: datasheets, alternates, Mouser, Farnell, element14, LCSC/JLCPCB, Altium, EasyEDA
  - `--with-hf` valide au 9 mars 2026 via `bshada/electronics.stackexchange.com`, `STEM-AI-mtl/Electrical-engineering` et `nick007x/eevblog-posts`
- [x] Verifier les doublons en fin de workflow dataset
  - refresh canonique: dedupe final + compteur `duplicates_removed`
  - packaging HF: dedupe final + `duplicates_removed_during_packaging`
  - consolidation distill/train: dedupe final + compteur dans reports/manifests batch
- [x] Rendre `components` dataset-ready pour HF
  - packaging canonique: `finetune/prepare_hf_dataset.py`
  - upload dataset: `finetune/upload_datasets_hf.sh`
  - package valide au 9 mars 2026 sous `finetune/hf_datasets/components/`
- [x] Rendre `components` live-ready sous revue manuelle
  - alias de review: `mascarade-components-review`
  - registre: `finetune/models_local/promotion_registry.json`
  - statut courant: `pending_manual_review`
  - la promotion live `mascarade-components` n est pas auto-approuvee

### Apres stabilisation
- [x] Integrer une premiere vague de modeles valides dans Mascarade via `merge -> gguf -> deploy -> smoke`
- [x] Etendre la promotion live aux domaines canoniques valides
  - aliases live publies: `mascarade-platformio`, `mascarade-stm32`, `mascarade-spice`, `mascarade-iot`, `mascarade-kicad`, `mascarade-freecad`, `mascarade-dsp`, `mascarade-embedded`, `mascarade-power`, `mascarade-emc`
- [ ] Approuver ou rejeter explicitement `mascarade-components-review` apres revue humaine
- [ ] Evaluer `Agent Zero` hors du pipeline critique
- [x] Integrer `selected_model.json` dans `batch_local.py` avec priorite `--student-model` > `selected_model.json` > fallback repo
- [x] Benchmarker `model_selector.py` vs selection manuelle sur cette machine
- [ ] Benchmarker localement les candidats remontes par la veille web live du 9 mars 2026 avant d elargir la politique auto
  - `Qwen/Qwen3-Coder-Next-Base`
  - `JetBrains/Mellum-4b-sft-all`
  - `deepseek-ai/DeepSeek-V3.2` en lane teacher-only / manuel
- [x] Migrer physiquement les caches/modeles legacy vers `/ai/llm` et supprimer les doublons restants
  - execute le 9 mars 2026 via `./scripts/migrate_models_to_llm.sh --execute --cleanup --link-home-cache`
  - resultat: `~/.cache/huggingface/hub -> /ai/llm/huggingface/hub`
  - resultat: `.tmp/hf-models` consolide dans `/ai/llm/watch_models`

## 4. Profils machine actifs

- le profil operateur n est plus fige sur P2000: il est maintenant derive du materiel detecte
- la racine canonique des modeles locale est maintenant:
  - `/ai/llm`
- conventions actives:
  - cache HF: `/ai/llm/huggingface/hub`
  - caches locaux: `/ai/llm/models_cache`
  - bench/watch: `/ai/llm/watch_models`
  - Apple LLM: `/ai/llm/apple-llm`
- classes machine actuellement gerees:
  - `gpu_24gb_plus`
  - `gpu_mid`
  - `gpu_small`
  - `gpu_tiny`
  - `cpu_only`
- `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`, `mistralai/Devstral-Small-2-24B-Instruct-2512` et `mistralai/Mistral-Small-3.1-24B-Base-2503` restent `teacher-only` dans ce pipeline
- validation locale teacher-only au 8 mars 2026:
  - `mistralai/Devstral-Small-2-24B-Instruct-2512`: charge et distille sur la 4090 via `local-hf` apres compactage/recovery local
  - `mistralai/Mistral-Small-3.1-24B-Base-2503`: charge sur la 4090 via `local-hf`, mais ne tient pas encore le schema JSON du smoke court; conserve en manuel uniquement
- validation mini-batch au 8 mars 2026:
  - `iot` (label historique `esp32`) -> `train=completed` avec teacher auto `Devstral`
  - `spice -> train=completed` avec teacher auto `Devstral`
  - `platformio` (label historique `pio`) -> `train=completed` avec teacher auto `Devstral`
  - manifest: `finetune/runs/devstral-mini-batch5_20260308_163309/manifest.json`
  - nuance historique: ce run batch validait la chaine complete, mais `platformio/pio` etait encore a `distilled_rows=0`
- validation `platformio/pio` apres correctif parseur au 8 mars 2026:
  - distill smoke: `.tmp/pio_devstral_fix.report.json` -> `distilled_rows=1`, `failed_source_rows=0`
  - batch mono-domaine: `finetune/runs/devstral-pio-fix_20260308_172519/manifest.json`
  - resultat: `distill=completed`, `train=completed`, `distilled_rows=1`, `failed_source_rows=0`
- benchmark slots GPU au 8 mars 2026:
  - training-only sur `stm32, spice, kicad, platformio`
  - source: `finetune/runs/sessions-4090-parallel-750x2_20260307_040828/manifest.json`
  - benchmark: `finetune/runs/qwen4b-slots-compare_20260308_171439/summary.json`
  - `slots=1`: `78.01s`, pic VRAM `9532 MiB`
  - `slots=2`: `42.01s`, pic VRAM `17119 MiB`
  - speedup `1.857x`, `0` echec dans les deux cas
- le batch choisit maintenant automatiquement:
  - le `teacher`
  - `gpu_slots`
  - `seq_len`
  - `student_max_samples`
- benchmark `model_selector.py` au 8 mars 2026:
  - benchmark live HF: `finetune/runs/model-selector-benchmark-live_20260308_213050/summary.json`
  - verdict: le selector et la politique manuelle convergent tous deux sur `Qwen/Qwen3.5-9B-Base` sur cette RTX 4090
  - correctifs relies:
    - cache/runtime state du selector deplace hors du repo quand il est sous pression (`/tmp/mascarade-finetune-state` en sandbox, `/dev/shm/mascarade-finetune-state` hors sandbox)
    - la politique hardware-adaptive garde maintenant le chemin GPU si le GPU NVIDIA est detecte/profilé, meme si `torch.cuda.is_available()` est bruité dans certains shells
- orchestration des prochains lots au 9 mars 2026:
  - entree canonique en lot utile: `./scripts/auto_chain_next_lots.sh`
  - entrée minimale plan/dry-run:
    - `./scripts/auto_chain_next_lots.sh --plan-only`
  - rapport auto de reference:
    - `finetune/runs/next-lots_20260309_063107/summary.json`
    - statut: watch/prune/cad/components tous `ok`
    - nuance: le smoke `kicad_mcp` est trace `unavailable`, pas `failed`, car le serveur source local n est pas peuple
  - prochain benchmark watch dry-run valide:
    - `JetBrains/Mellum-4b-sft-all`
    - commande résolue via `./scripts/auto_chain_next_lots.sh` puis `./scripts/bench_watch_candidate.sh`
  - boucle auto live lancee:
    - commande: `./scripts/auto_chain_next_lots_loop.sh --label auto-next-lots-live --iterations 1 --sleep-seconds 900 --max-blocked-streak 160 --max-failed-streak 3 --max-ok-cycles 1 --pass-through-arg --skip-watch-refresh`
    - premier cycle: `finetune/runs/auto-next-lots-live_20260309_072329_cycle_1/manifest.json`
    - etat: `JetBrains/Mellum-4b-sft-all` bloque proprement (`status=blocked`, rc=2) tant que la lane `tuning-party-hf` occupe le GPU
  - meme hors reseau, le lot retombe maintenant proprement sur `selected_model.json` si aucun `student_watch` frais n est disponible
  - benchmark reel execute sur candidat cache:
    - `JetBrains/Mellum-4b-base`
    - run: `finetune/runs/watch-bench-JetBrains-Mellum-4b-base_stm32_20260309_055311/`
    - verdict: stockage/caches OK via `/ai/llm`
    - correctif applique: chargement quantized 4-bit force full-GPU pour les petits checkpoints sur GPU 24 Go+
    - rerun: `finetune/runs/watch-bench-JetBrains-Mellum-4b-base_stm32_20260309_055500/`
    - verdict du rerun: le loader passe, puis OOM car la VRAM est deja monopolisee par `tuning-party-hf` (`Qwen/Qwen3.5-9B-Base`)
    - correctif applique: `bench_watch_candidate.sh` bloque maintenant en preflight si la VRAM libre est insuffisante
    - prochain lot utile: relancer le benchmark Mellum quand la lane `tuning-party-hf` est finie, ou bencher `JetBrains/Mellum-4b-sft-all` dans une fenetre GPU libre via `./scripts/auto_chain_next_lots.sh --execute --continue-on-error`
- objectifs teacher auto disponibles:
  - `fast`
  - `balanced`
  - `quality`
- la promotion live est disponible en opt-in via `--auto-promote`
- promotion live validee au 8 mars 2026:
  - alias publies: `mascarade-platformio`, `mascarade-stm32`, `mascarade-spice`, `mascarade-iot`, `mascarade-kicad`, `mascarade-freecad`, `mascarade-dsp`, `mascarade-embedded`, `mascarade-power`, `mascarade-emc`
  - sources:
    - `platformio` -> `finetune/models_local/platformio_sessions-4090-parallel-750x2_20260307_040828`
    - `stm32` -> `finetune/models_local/stm32_sessions-4090-parallel-750x2_20260307_040828`
    - `spice` -> `finetune/models_local/spice_sessions-4090-parallel_20260307_035624`
    - `iot` -> `finetune/models_local/iot_sessions-4090-parallel-750x2_20260307_040828`
    - `kicad` -> `finetune/models_local/kicad_sessions-4090-parallel-750x2_20260307_040828`
    - `freecad` -> `finetune/models_local/freecad_sessions-4090-parallel-750x2_20260307_040828`
    - `dsp` -> `finetune/models_local/dsp_sessions-4090-parallel_20260307_035624`
    - `embedded` -> `finetune/models_local/embedded_sessions-4090-parallel-750x2_20260307_040828`
    - `power` -> `finetune/models_local/power_sessions-4090-parallel-750x2_20260307_040828`
    - `emc` -> `finetune/models_local/emc_sessions-4090-parallel-750x2_20260307_040828`
  - registre: `finetune/models_local/promotion_registry.json`
  - note d infra: le deploy bascule maintenant automatiquement sur l Ollama hote si le conteneur monte `/root/.ollama` en lecture seule
  - note d infra bis: si le filesystem du repo est plein, la promotion stage automatiquement le merge/GGUF sous `/dev/shm/mascarade-promotion`
  - validation runtime additionnelle: `mascarade-iot` smoke OK via `ollama run` et via `POST /api/agents/send`
  - validation runtime additionnelle: `mascarade-kicad` smoke OK via `ollama run` et via `POST /api/agents/send`
  - validation runtime additionnelle: `mascarade-freecad`, `mascarade-dsp` et `mascarade-embedded` smoke OK via `ollama run` et via `POST /api/agents/send`
  - validation runtime additionnelle: `mascarade-power` et `mascarade-emc` smoke OK via `ollama run` et via `POST /api/agents/send`
- quality gate dataset actif au 9 mars 2026:
  - mode par defaut: `fail`
  - bloque les datasets vraiment trop petits (`<4` rows), trop repetitifs en prompts, ou trop verbeux au `p95`
  - laisse des warnings sur les IDs syntheses et l uniformite du prompt systeme
  - validation locale actuelle: `components_chat.jsonl` passe en mode enrichi `--with-hf` (`30` rows); `stm32_chat.jsonl` passe avec warnings
- refresh dataset actif au 9 mars 2026:
  - workflow canonique = `mascarade-datasets/` si present, sinon `finetune/datasets/build_*`
  - un brief de recherche web par domaine est ecrit dans `finetune/research/`
  - les briefs embarquent maintenant docs officielles, GitHub officiels, sources logiciel et racines datasheet/vendor
  - les anciens builders `finetune/build_components_dataset.py` et `finetune/build_freecad_dataset.py` sont retires
- `components` au 9 mars 2026:
  - dataset source regenere et valide en mode `--with-hf` (`30` rows, quality gate `passed`)
  - package HF pret dans `finetune/hf_datasets/components/`
  - promotion staged sous `mascarade-components-review`
  - smoke de review OK, mais validation live finale gardee derriere une revue manuelle

### Tuning Party HF — 9 mars 2026

- [x] Upgrade `transformers` 4.57.6 → 5.3.0 (vllm avait downgrade, Qwen3.5 `qwen3_5` model_type non reconnu)
- [x] Verifier compatibilite: torch, transformers, peft, trl, vllm importent sans erreur
- [x] Audit complet datasets enrichis (143K rows, 11 domaines) — tous passent le quality gate
  - stm32: 2688 rows, 0 dups, passed
  - freecad: 3991 rows, 0 dups, warning (single system prompt)
  - iot: 4614 rows, 0 dups, passed
  - dsp: 5447 rows, 0 dups, passed
  - kicad: 6919 rows, 0 dups, passed
  - emc: 7055 rows, 0 dups, passed
  - platformio: 6997 rows, 303 dups (4.3%), warning (single system prompt)
  - embedded: 15826 rows, 0 dups, passed
  - power: 16894 rows, 0 dups, passed
  - spice: 72852 rows, 0 dups, passed
  - components: 30 rows, 0 dups, passed
- [x] Deep audit format/content: aucun champ vide, tous les rows ont system/user/assistant
- [x] Lancer Phase A SFT (batch_phase_a.sh) — en cours, stm32 en premier, ~20s/step
  - Modele: Qwen/Qwen3.5-9B-Base
  - Strategie smart: 3ep petits, 1ep gros, spice cap 20K
  - Log: `runs/phase_a_full_20260309_*.log`
- [x] Creer `batch_full_pipeline.sh` — enchaine Phase A → merge/deploy → Phase B → Phase C
  - Supporte `--skip-phase-a`, `--only-phase-b`, `--only-phase-c`
  - Rapport de statut en fin de pipeline
- [x] Executer un lot utile complet `next_finetune_lots`
  - rapport: `finetune/runs/next-lots_20260309_063107/summary.json`
  - `cad_tool_smoke_tmpfs` valide `kicad-cli`, `freecad`, `platformio` sur tmpfs
  - `kicad_mcp` reste `unavailable` tant que `finetune/kicad_mcp_server/` n a pas ses sources
- [x] Exécuter une passe auto vers `JetBrains/Mellum-4b-sft-all` via `auto_chain_next_lots`
  - commande: `./scripts/auto_chain_next_lots.sh --execute --iterations 1 --continue-on-error`
  - artefact live courant: `finetune/runs/auto-next-lots-live_20260309_072329_cycle_1/manifest.json`
  - statut: `status=blocked` (preflight GPU), en attente de libération de la 4090 via `tuning-party-hf`
  - correction récente: fallback auto vers `selected_model.json` en cas de watch report indisponible (`finetune/runs/auto-next-lots_20260309_072309/manifest.json`).
- [x] Durcir l’enchainement continu:
  - `scripts/auto_chain_next_lots_loop.sh` bloque désormais `--report-dir` en pass-through et applique un backoff exponentiel sur répétitions `blocked`.
- [x] Exemple de preuve continue: `finetune/runs/auto-next-lots_20260309_071721_cycle_1/manifest.json`, `...071741_cycle_2/manifest.json`, `...071801_cycle_3/manifest.json`.
- [ ] Phase A: attendre completion (~22h)
- [ ] Phase B: rejection sampling (apres Phase A)
  - prerequis: `gcc-arm-none-eabi` ✅ (15.2.0), `ngspice` ✅ (installs 2026-03-27)
  - domaines prioritaires: stm32, embedded, spice, kicad, platformio (validateurs deterministes)
  - script: `finetune/batch_phase_b.sh` (prêt 2026-03-27)
- [ ] Phase C: DPO training (apres Phase B)
  - methode: ORPO (pas de reference model, économise ~3GB VRAM pour Qwen2.5-3B)
  - script: `finetune/batch_phase_c.sh` (prêt 2026-03-27)
- [ ] Phase D: publication HF adapters sous `clemsail/mascarade-*-lora`
  - script: `finetune/batch_phase_d.sh` (prêt 2026-03-27)
  - chaîne complète: `finetune/batch_phases_bcd.sh`
- [ ] Approuver ou rejeter explicitement `mascarade-components-review` apres revue humaine
- [ ] Benchmarker candidats veille web: Qwen3-Coder-Next-Base, Mellum-4b, DeepSeek-V3.2
  - boucle live deja lancee pour `JetBrains/Mellum-4b-sft-all`
  - prochain debloquage attendu quand `tuning-party-hf` libere la 4090
- [x] Repeupler `finetune/kicad_mcp_server/` ou rediriger la stack vers le vrai serveur KiCad MCP pour sortir `kicad_mcp` du statut `unavailable` — `finetune/kicad_mcp_server/` présent avec `PHASE_2_COMPLETE.md` + `package.json`
- [x] Executer `./scripts/migrate_models_to_llm.sh --execute --cleanup --link-home-cache`

## 5. Ordre recommande

1. Attendre fin Phase A SFT (~22h).
2. Lancer `./scripts/auto_chain_next_lots.sh --plan-only` pour recalculer le lot utile a partir du dernier rapport vert `next-lots_20260309_063107`.
3. Laisser tourner la boucle live `./scripts/auto_chain_next_lots_loop.sh --label auto-next-lots-live --iterations 1 --sleep-seconds 900 --max-blocked-streak 160 --max-failed-streak 3 --max-ok-cycles 1 --pass-through-arg --skip-watch-refresh`.
   - preuve courante: `finetune/runs/auto-next-lots-live_20260309_072329_cycle_1/manifest.json` (`status=blocked`, `runs_blocked=1`).
4. Quand la 4090 est libérée, laisser la boucle lancer le benchmark `JetBrains/Mellum-4b-sft-all` sans intervention manuelle.
5. Repeupler `finetune/kicad_mcp_server/` ou brancher le vrai serveur KiCad MCP si on veut une couverture MCP automatique complete.
5. Revue humaine puis `approve` ou rejet de `mascarade-components-review`.
6. Publication HF des adapters valides.
