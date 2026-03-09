# Finetuning Model Shortlist

Date de reference: 2026-03-09

Cette shortlist sert de base au profil hardware-adaptive du pipeline local.
Elle se limite aux modeles open-weight recents qui ont un sens pratique sur la machine detectee.

## Workflow de veille web

- le workflow de selection inclut maintenant une veille web via `finetune/model_selector.py --watch --refresh --task code`
- cette veille interroge les releases recentes des auteurs de confiance sur le Hub (`Qwen`, `mistralai`, `deepseek-ai`, `JetBrains`)
- elle n injecte pas automatiquement ces nouveaux candidats dans la politique auto: elle produit d abord un `model_watch_report.json` a revoir avant validation locale
- `run_local.py` et `batch_local.py` rafraichissent maintenant automatiquement cette veille et la selection student si aucun modele explicite n est fourni et que le cache TTL est stale

## Machine actuelle detectee

- GPU: `NVIDIA GeForce RTX 4090`
- VRAM: `24564 MiB`
- driver: `580.126.09`

## Politique retenue

- `student` local par defaut sur GPU 24 Go: `Qwen/Qwen3.5-9B-Base`
- `teacher-only` local haut de gamme: `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`
- `teacher-only` recent alternatif: `mistralai/Devstral-Small-2-24B-Instruct-2512`
- `teacher-only` recent alternatif base: `mistralai/Mistral-Small-3.1-24B-Base-2503`
- fallback local stable si aucun teacher HF lourd n est disponible: `ollama/qwen2.5:14b`
- en selection auto, ces gros teachers `local-hf` restent en `device_map=auto`; les seuls teachers valides ici en vrai `cuda:0` sont `Qwen/Qwen2.5-7B-Instruct` et `Qwen/Qwen3-4B-Instruct-2507`

## Objectifs teacher auto

- `balanced`:
  - priorite a `Qwen/Qwen2.5-7B-Instruct`, puis `Qwen/Qwen3-4B-Instruct-2507`
  - utile pour les batchs locaux ou le debit compte autant que la qualite

- `fast`:
  - priorite a `Qwen/Qwen3-4B-Instruct-2507`, puis `Qwen/Qwen2.5-7B-Instruct`
  - utile pour `teacher GPU -> student CPU` et les runs iteratifs

- `quality`:
  - priorite a `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`, puis `Devstral 24B`, puis `Mistral 24B`
  - utile pour teacher-only ou distillation plus lente mais plus ambitieuse

- sur des domaines tres code-heavy, `Devstral 24B` peut etre remonte plus haut dans les modes `balanced` et `quality`

## Raison par modele

### Student

- `Qwen/Qwen3.5-9B-Base`
  - role: `student`
  - raison: checkpoint base recent, bon fit pour LoRA/QLoRA sur une seule 4090
  - statut local: deja en cache
  - benchmark selector vs manuel valide au 8 mars 2026:
    - artefact: `finetune/runs/model-selector-benchmark-live_20260308_213050/summary.json`
    - verdict: le selector live HF et la politique manuelle convergent sur ce meme student

- `Qwen/Qwen3-8B`
  - role: `student` alternatif
  - raison: dense recent, deja valide en local dans ce repo
  - statut local: adapte au profil parallelise 4090

- `Qwen/Qwen3-4B-Instruct-2507`
  - role: `student` alternatif plus parallele
  - raison: utile quand l objectif est le debit plutot que la qualite solo maximale
  - promotion live validee au 8 mars 2026:
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
    - quantization: `q4_k_m`
    - smoke runtime: OK via Ollama hote
    - integration Mascarade: tous les aliases live publies sont valides via `POST /api/agents/send`

### Teacher-only

- `Qwen/Qwen3.5-35B-A3B-GPTQ-Int4`
  - role: `teacher-only`
  - raison: meilleur gros teacher local deja cadre dans le pipeline; pas un bon student local QLoRA ici
  - statut local: deja en cache

- `mistralai/Devstral-Small-2-24B-Instruct-2512`
  - role: `teacher-only`
  - raison: modele recent oriente code/agentic; bon candidat de distillation locale si la VRAM suit
  - statut local: telecharge et present en cache
  - validation locale actuelle: charge correctement en `local-hf` sur la 4090, genere sur GPU, et le smoke compact produit maintenant `distilled_rows=1` apres recovery local des JSON tronques
  - politique auto actuelle: prioritaire sur les lots majoritairement code-heavy (`stm32`, `embedded`, `platformio`, `iot`, `kicad`, `freecad`) en profil `gpu_24gb_plus`
  - batch reel valide: `iot spice platformio` (labels historiques `esp32 spice pio`) termine avec `train=completed` sur les 3 domaines sous teacher auto `Devstral`
  - correctif `platformio` valide au 8 mars 2026: smoke direct `platformio` -> `distilled_rows=1`, puis batch mono-domaine `pio` -> `distill=completed`, `train=completed`

- `mistralai/Mistral-Small-3.1-24B-Base-2503`
  - role: `teacher-only`
  - raison: base recente 24B utile comme teacher local et reference Mistral
  - statut local: snapshot complet en cache local
  - validation locale actuelle: charge correctement en `local-hf` sur la 4090, mais le smoke court echoue encore a produire un JSON conforme; a garder experimental/reference
  - politique auto actuelle: exclu du mode auto, usage manuel seulement tant que le schema JSON n est pas stabilise

## Candidats a surveiller via la veille web

Sortie live validee le 9 mars 2026 via:
`python finetune/model_selector.py --watch --refresh --task code --watch-top 8 --top 6 --auto`

- `Qwen/Qwen3-Coder-Next-Base`
  - role: `manual_review`
  - raison: nouvelle lane Qwen code/base remontee par la veille live, potentiellement interessante comme futur student mais taille/fit a verifier localement
  - statut pipeline: a benchmarker avant toute entree dans la politique auto

- `JetBrains/Mellum-4b-base`
  - role: `student_watch`
  - raison: base dense recente specialisee code, explicitement orientee fine-tuning et completion, bonne taille pour un benchmark local
  - statut pipeline: a benchmarker, pas encore dans la politique auto

- `deepseek-ai/DeepSeek-V3.2`
  - role: `teacher_watch`
  - raison: release DeepSeek recente tres forte sur code/agent, publiee en lane FP8 et reservee a la veille teacher/manual
  - statut pipeline: teacher-only / manuel uniquement

## Sources primaires

- Qwen3.5-9B-Base: <https://huggingface.co/Qwen/Qwen3.5-9B-Base>
- Qwen3.5-35B-A3B-GPTQ-Int4: <https://huggingface.co/Qwen/Qwen3.5-35B-A3B-GPTQ-Int4>
- Devstral-Small-2-24B-Instruct-2512: <https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512>
- Mistral-Small-3.1-24B-Base-2503: <https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Base-2503>
- Qwen3-Coder-Next-Base: <https://huggingface.co/Qwen/Qwen3-Coder-Next-Base>
- Mellum-4b-base: <https://huggingface.co/JetBrains/Mellum-4b-base>
- DeepSeek-V3.2: <https://huggingface.co/deepseek-ai/DeepSeek-V3.2>

## Impact dans le code

- `finetune/auto_policy.py` choisit le profil machine, le `teacher` et l autotune student
- pour les gros teachers `local-hf`, `finetune/auto_policy.py` garde maintenant `local_hf_device=auto` par defaut et conserve le profil GPU tant que la machine NVIDIA est detectee/profilée, meme si le probe `torch.cuda.is_available()` est bruité dans certains shells
- `finetune/batch_local.py` consomme ces decisions et les trace dans le manifest
- `finetune/run_local.py` reutilise le meme choix student si aucun `--model` n est force
- `finetune/train_local.py` et `finetune/train_cpu.py` refusent explicitement les modeles `teacher-only` comme students
- `finetune/model_selector.py` garde maintenant son state runtime hors du repo si besoin (`/tmp` en sandbox, `/dev/shm` hors sandbox), ce qui le rend robuste sur un FS repo sature
- `finetune/model_selector.py --watch` ajoute maintenant une veille web recente et ecrit `model_watch_report.json` dans ce state runtime
- `finetune/run_local.py` et `finetune/batch_local.py` rafraichissent cette veille/selection quand le cache TTL est stale et qu aucun student explicite n est fourni
