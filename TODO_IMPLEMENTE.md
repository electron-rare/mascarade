# TODO IMPLEMENTE

Etat de reference du chantier fine-tuning/distillation local au 6 mars 2026.

## 1. Deja implemente

### Pipeline local
- [x] Point d'entree unique pour lancer le fine-tuning local CPU/GPU
- [x] Support `LoRA/QLoRA` local avec `venv_tuning`
- [x] Fallback CPU utilisable quand CUDA est indisponible
- [x] Smoke tests reels valides en CPU et en GPU

### Distillation teacher -> student
- [x] Pipeline complet `distill -> merge -> train`
- [x] Support teacher via API locale sur `http://127.0.0.1:8100`
- [x] Support `mistral` comme teacher principal
- [x] Mode JSON strict cote teacher Mistral
- [x] Retries sur JSON invalide et erreurs reseau/transitoires
- [x] Rapport de distillation JSON avec succes/echecs
- [x] Export optionnel des rows en echec

### Robustesse du routeur
- [x] Requetes teacher strictes sans fallback silencieux vers `bedrock`
- [x] Garde-fou si le provider retourne autre chose que celui demande
- [x] Cache evite sur les requetes strictes cross-provider
- [x] Timeout Mistral allonge pour les gros prompts

### Verbosite et suivi
- [x] Flags `--verbose` et `--quiet`
- [x] Progress bars cote tokenization/training
- [x] Logs plus lisibles cote distillation
- [x] Scripts de debug pour le core local sur `8100`

### Parallellisation du pipeline
- [x] Concurrence configurable pour la distillation teacher
- [x] Tokenization multi-workers cote training
- [x] Orchestrateur batch multi-domaines ajoute
- [x] Aliases de domaines:
  - `esp32 -> iot`
  - `pio -> platformio`
- [x] Manifest d'execution par run batch
- [x] Reprise `--resume` sur le batch
- [x] Queue GPU avec limite de trainings paralleles
- [x] Garde-fou VRAM avant lancement d'un second training GPU
- [x] Wrapper shell pour lancer le batch multi-domaines

## 2. Scripts et entrees disponibles

- [x] `finetune/run_local.py`
- [x] `finetune/distill_dataset.py`
- [x] `finetune/distill_and_train.py`
- [x] `finetune/batch_local.py`
- [x] `finetune/batch_status.py`
- [x] `scripts/finetune_local.sh`
- [x] `scripts/distill_and_train.sh`
- [x] `scripts/parallel_domains_gpu_queue.sh`
- [x] `scripts/debug_core_8100.sh`
- [x] `scripts/debug_mistral_smoke.sh`

## 3. Etat reel du batch parallele

### Ce qui passe deja
- [x] `kicad` valide en distillation Mistral + training GPU local
- [x] `spice` passe sur le chemin distill + merge en smoke test batch
- [x] `platformio` passe sur le chemin distill + merge en smoke test batch
- [x] `esp32` alias `iot` passe maintenant sur le chemin distill + merge en smoke test batch
- [x] Le dataset source `iot` est valide apres normalisation `ensure_row_ids()`

### Ce qui reste a verrouiller
- [ ] Valider la phase `train` de bout en bout sur un run batch `esp32 spice pio`
- [ ] Documenter clairement la reprise d'un run batch interrompu avec `--resume`
- [ ] Mesurer si `2` trainings GPU paralleles apportent un gain reel sur Quadro P2000
- [ ] Ajouter un resume CLI/rapport qui distingue `distill completed` de `train pending`

### Verification au 6 mars 2026
- [x] `finetune/runs/smoke_batch_20260306_191758`: `esp32`, `spice`, `pio` en `distill=completed`
- [x] `finetune/runs/smoke_batch_gpu_20260306_193427`: `esp32`, `spice`, `pio` en `distill=completed`
- [x] `finetune/runs/smoke_batch_gpu2_20260306_195107`: `esp32`, `spice`, `pio` en `distill=completed`
- [ ] Les manifests ci-dessus restent en `train=pending`; l'entrainement batch complet n'est donc pas encore valide de bout en bout

## 4. TODO Agent Zero

Objectif: cadrer si `Agent Zero` doit rester un sujet d'etude, un outil de debug, ou une vraie brique d'orchestration dans Mascarade.

- [ ] Identifier precisement le perimetre `Agent Zero` vise ici
- [ ] Comparer `Agent Zero` avec l'orchestrateur local deja implemente dans `finetune/batch_local.py`
- [ ] Definir si `Agent Zero` sert a:
  - orchestration multi-agents
  - planification de jobs
  - supervision d'execution
  - experimentation locale
- [ ] Faire un POC isole, sans melanger tout de suite la chaine de fine-tuning existante
- [ ] Evaluer le cout de maintenance avant integration repo
- [ ] Definir les garde-fous:
  - isolation des secrets
  - limites CPU/GPU
  - timeout des jobs
  - logs et reprise

## 5. Prochain ordre de travail recommande

1. Terminer un batch `esp32 spice pio` avec phase `train` complete et logs conserves.
2. Ajouter un resume d'etat batch lisible (`distill completed`, `train running`, `train pending`, `failed`).
3. Lancer un vrai batch multi-domaines avec queue GPU a `1`.
4. Mesurer ensuite un mode experimental a `2` trainings GPU paralleles.
5. Cadrer `Agent Zero` separement, apres stabilisation du pipeline local.

## 6. Cockpit frontend deja implemente

### Shell et navigation
- [x] Shell React unifie avec sidebar desktop, drawer mobile et mobile dock
- [x] Raccourcis clavier `Alt+1..9`
- [x] Panneau session/auth clavier-safe
- [x] Fond visuel Matrix/CRT conserve comme direction par defaut

### Pages cockpit
- [x] Refonte `Dashboard`
- [x] Refonte `Playground`
- [x] Refonte `Agents`
- [x] Refonte `Agent Detail`
- [x] Refonte `Orchestrate`
- [x] Refonte `Metrics`
- [x] Refonte `Infrastructure`
- [x] Refonte `Notion Browser`
- [x] Refonte `ComfyUI`
- [x] Lane `Logs` ajoutee au cockpit

### Agent Zero
- [x] `agent-zero` ajoute comme agent builtin dans le core
- [x] `agent-zero` expose visiblement dans le cockpit
- [x] `agent-zero` mis en avant dans `Dashboard`, `Agents`, `Agent Detail`, `Orchestrate`
- [x] CTA de cadrage incident vers `agent-zero` ajoutes dans les surfaces ops

## 7. Observability deja implemente

### Trace native Mascarade
- [x] `run_id` stable sur les runs d'orchestration
- [x] Evenements inter-agent structures dans le core
- [x] Buffer recent de traces dans le core
- [x] Exposition des traces via routes core dediees

### Facade ops API
- [x] `GET /api/ops/monitor`
- [x] `GET /api/ops/summary`
- [x] `GET /api/ops/sources`
- [x] `GET /api/ops/logs/recent`
- [x] `GET /api/ops/agent-traces/recent`
- [x] `GET /api/ops/agent-traces/:runId`

### Surface cockpit
- [x] Vue `Logs` pour lire incidents services + traces inter-agent
- [x] Panneau `live run trace` dans `Orchestrate`
- [x] Liens directs vers `Logs` depuis `Dashboard`, `Metrics`, `Infrastructure`

### Infra complementaire scaffolded
- [x] Modules `loki`, `promtail`, `otel-collector`
- [x] Configs `deploy/loki`, `deploy/promtail`, `deploy/otel-collector`
- [x] Spec produit cockpit dans `docs/FRONTEND_SPEC.md`
- [x] Spec technique observability dans `docs/OBSERVABILITY_ARCHITECTURE.md`

## 8. Backlogs actifs a suivre

- [x] Backlog fine-tuning detaille dans `TODO_TUNNING_PARTY.md`
- [x] Backlog cockpit/ops detaille dans `TODO_COCKPIT_OPS.md`
