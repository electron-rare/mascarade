# TODO IMPLEMENTE

Etat de reference du chantier local recale au 8 mars 2026.

Note de contexte multi-repo:
- l'ownership produit et la release canonique du cockpit vivent maintenant dans
  `crazy_life`
- `mascarade/web` reste un bridge/snapshot
- ce fichier sert surtout a figer ce qui est vraiment implemente cote runtime
  local et fine-tuning

## 1. Pipeline fine-tuning local stabilise

- [x] Point d'entree unique CPU/GPU avec `venv_tuning`
- [x] Pipeline complet `distill -> merge -> train -> export GGUF -> import Ollama`
- [x] Teacher Mistral via API locale avec JSON strict, retries et logs lisibles
- [x] `--resume`, `batch_status.py`, manifests de run et queue GPU versionnes
- [x] Verrou GPU global machine pour eviter les chevauchements de trainings
- [x] Garde-fous VRAM et reprise des statuts batch orphelins

## 2. Etat reel du batch canonique

- [x] Le batch canonique `p2000_bench_gpu1_fixed_20260308_143343` est `completed`
- [x] `esp32`, `spice` et `pio` sont tous en `train=completed`
- [x] Promotions locales disponibles:
  - `esp32_local_v1`
  - `spice_local_v1`
  - `pio_local_v1`
- [x] Export GGUF et chargement Ollama verifies sur les modeles promus
- [x] `promote_model.py` accepte maintenant les manifests batch sans `kind`

## 3. Agent Zero

- [x] `agent-zero` evalue comme brique hors pipeline critique
- [x] `POST /api/agents/agent-zero/run` valide sur le chemin simple
- [x] `POST /api/agents/agent-zero/copilot` accepte un contexte operateur structure
- [x] Le mode `operator copilot` est expose dans `OpsHub`, `Logs` et `Orchestrate`
- [x] Les traces d'orchestration associees restent visibles dans le cockpit ops
- [x] `Agent Zero` reste volontairement hors pipeline critique et hors scheduling fine-tuning
- [ ] N'etendre ses actions que si un besoin operateur explicite depasse le mode copilot actuel

## 4. Cockpit et observabilite deja implemente

- [x] Cockpit React unifie avec `Dashboard`, `Agents`, `Orchestrate`, `Logs`, `OpsHub`
- [x] Surfaces runtime `knowledge-base` et `cad` en place a la place des anciennes surfaces `notion`
- [x] Trace native `run_id`, timeline operateur et facade ops complete
- [x] `ops-agent`, Loki, Promtail, OTel Collector, Prometheus, Grafana et Langfuse verifies
- [x] `Tempo` comme backend traces Grafana et `blackbox-exporter` pour les surfaces sans `/metrics`
- [x] `Grafana` et `Langfuse` accessibles via `edge-proxy` avec auth operateur dediee
- [x] `SearXNG`, `Paperless-ngx` et `Karakeep` deploies via `deploy/phase2`, gardes en bind local-first et publies uniquement derriere `edge-proxy`
- [x] `ZeroClaw` installe nativement sur la VM, demarrable a la demande, avec `zeroclaw.saillant.cc` en surface live et `zeroclaw-docs.saillant.cc` / `langgraph.saillant.cc` en surfaces runbook proxifiees
- [x] Smoke reel `ZeroClaw` valide via `POST /webhook`, avec reponse modele retournee par le fallback `OpenRouter`

## 5. Providers cloud additionnels

- [x] `openai` active et validee sur un smoke strict (`provider=openai`, `strategy=specific`)
- [x] `claude` configuree cote VM et visible dans l'admin providers
- [x] `google` configure avec `GOOGLE_AUTH_MODE=api_key` et visible dans l'admin providers
- [ ] `claude` reste bloquee par un probleme externe de credit Anthropic
- [ ] `google` reste bloquee tant que l'API `generativelanguage.googleapis.com` n'est pas active sur le projet associe

## 6. Backlogs encore utiles

- [x] Backlog fine-tuning detaille dans `TODO_TUNNING_PARTY.md`
- [x] Backlog cockpit/ops detaille dans `TODO_COCKPIT_OPS.md`
- [x] Plan global d'execution recale dans `docs/EXECUTION_PLAN_2026-03-07.md`

## 7. Prochain ordre recommande

1. Ne pas rouvrir de nouveau lot local par defaut: le socle runtime/ops est livre.
2. Garder `Agent Zero` hors chemin critique.
3. Ne rouvrir les E2E differes que sur besoin explicite.
4. Traiter seulement les restes externes ou optionnels: billing `Anthropic`, activation API Google, et consolidation du worktree `/Users/electron/mascarade` sur le Mac operateur avant tout `pull`.
