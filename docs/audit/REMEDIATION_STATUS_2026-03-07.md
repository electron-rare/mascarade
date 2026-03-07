# Remediation Status — 2026-03-07

## Scope
Statut d'exécution des actions issues de `REMEDIATION_BACKLOG_2026-03-07.md`.

## Global status
- Audit exécuté: **Oui**
- Remédiations appliquées pendant ce tour: **Oui**
- Nature du travail réalisé: stabilisation machine, réactivation auth `mascarade`, correction ciblée du flux SSE ops, réduction du bruit cockpit ops, reprise du TODO fine-tuning
- Bloc différé post-stabilisation structuré: **Oui**

## J0 detail

### R-001 — Réduire la pression machine
- Status: **Partial**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/host_free_h.txt`
  - `AUDIT_EVIDENCE_2026-03-07/host_top_cpu_processes.txt`
- Outcome:
  - les jobs `train_cpu.py`, `train_parallel.sh`, `batch_local.py --device cpu` et `distill_dataset.py` actifs ont ete termines proprement;
  - la RAM utilisee est retombee d'un etat critique a un etat stable;
  - le swap reste charge et doit encore etre purge manuellement ou au prochain redemarrage/fenetre systeme.

### R-002 — Réactiver l'auth sur `mascarade`
- Status: **Done**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_api_runtime_env_selected.txt`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_api_key_nonempty.txt`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_ops_summary_noauth.txt`
- Outcome:
  - `MASCARADE_API_KEY` a ete renseignee dans `.env`;
  - `mascarade-api` et `mascarade-core` ont ete recrees;
  - `GET /api/ops/summary` repond desormais `401` sans token et `200` avec Bearer valide.

### R-003 — Corriger les faux verts runtime/logs
- Status: **Partial**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_docker_logs_key_signals.txt`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_api_ops_summary.json`
- Outcome:
  - le flux `GET /api/ops/logs/stream` a ete durci cote proxy SSE et allégé cote client live;
  - un test SSE authentifie court ne reproduit plus l'erreur `edge-proxy` sur `upstream prematurely closed connection`;
  - `core_metrics.fallback.total_failures` est revenu a `0` apres redemarrage;
  - `promtail` garde encore des erreurs transitoires liees au churn/restart conteneur et reste a surveiller.

### R-004 — Rendre les tests Python exécutables
- Status: **Not started**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_core_pytest_q.txt`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_core_pytest_venv.txt`
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_pytest.txt`
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_unittest_discover_setup_repo.txt`

### R-005 — Geler l'état publiable de `crazy_life`
- Status: **Not started**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/crazy_life_git_status.txt`
  - `AUDIT_EVIDENCE_2026-03-07/crazy_life_github_workflows.txt`

## J7 detail

### R-006 — Stabiliser l'observabilité machine dans le cockpit ops
- Status: **Partial**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/ops_agent_health.json`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_api_ops_summary.json`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_api_ops_monitor.json`
  - `AUDIT_EVIDENCE_2026-03-07/host_nvidia_smi.txt`
- Outcome:
  - `ops-agent` filtre désormais par défaut le bruit `exec_*` Docker, une partie des probes HTTP internes et une partie du churn journald lié aux recreates conteneur;
  - la façade API relaie le paramètre `include_routine` pour récupérer le flux brut seulement quand c'est utile;
  - `/api/ops/summary` et `/logs/recent` sont plus lisibles, avec les alertes `promtail` qui ressortent mieux;
  - le gap MCP `api/conteneur` est désormais traité: les probes MCP sont exécutés par `ops-agent`, qui voit `Kill_LIFE`, le socket Docker et le runtime KiCad conteneurisé, puis relaye leur synthèse vers l'API;
  - il reste à ajouter un probe GPU réel et à valider le mode live des MCP qui dépendent encore de secrets absents (`notion`, `github-dispatch`).

### R-007 — Rendre les builds hermétiques et non salissants
- Status: **Not started**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_git_status.txt`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_git_status_post_checks.txt`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_git_diff_stat_post_checks.txt`
  - `AUDIT_EVIDENCE_2026-03-07/mascarade_web_build.txt`

### R-008 — Réduire la dérive locale de `Kill_LIFE`
- Status: **Not started**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_git_status.txt`
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_git_metrics.txt`
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_git_diff_stat.txt`
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_untracked_module_imports.txt`
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_docs_writes_scan.txt`

### R-009 — Décider du sort de `ai-agentic-embedded-base`
- Status: **Not started**
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_git_diff_stat.txt`
  - `AUDIT_EVIDENCE_2026-03-07/kill_life_github_workflows.txt`

## J30 detail

### R-010 — Clarifier le contrat multi-repo
- Status: **Deferred (post-stabilisation)**
- Blocking condition:
  - attendre la mise sous controle de `R-001` a `R-009`
- References:
  - `REMEDIATION_BACKLOG_2026-03-07.md#r-010--clarifier-le-contrat-multi-repo`
  - `../../plan.md`
  - `../../../crazy_life/plan.md`

### R-011 — Renforcer la CI de `crazy_life` et `Kill_LIFE`
- Status: **Deferred (post-stabilisation)**
- Blocking condition:
  - attendre la stabilisation du chemin de publication canonique et de la cartographie multi-repo
- References:
  - `REMEDIATION_BACKLOG_2026-03-07.md#r-011--renforcer-la-ci-de-crazy_life-et-kill_life`

### R-012 — Réduire la surface exposée au niveau hôte
- Status: **Deferred (post-stabilisation)**
- Blocking condition:
  - attendre la reactivation d'une auth effective sur `mascarade` et la stabilisation du cockpit ops
- References:
  - `REMEDIATION_BACKLOG_2026-03-07.md#r-012--reduire-la-surface-exposee-au-niveau-hote`

### R-013 — Workflow Editor Lot 2
- Status: **Deferred (post-stabilisation)**
- Blocking condition:
  - attendre `R-010` et un chemin publiable geler pour `crazy_life`
- References:
  - `REMEDIATION_BACKLOG_2026-03-07.md#r-013--workflow-editor-lot-2`
  - `../../plan.md`
  - `../../../crazy_life/plan.md`

### R-014 — Fine-tuning hors pipeline critique
- Status: **Deferred (post-stabilisation)**
- Blocking condition:
  - attendre un run batch complet valide et un runbook operateur fine-tuning gele
- References:
  - `REMEDIATION_BACKLOG_2026-03-07.md#r-014--fine-tuning-hors-pipeline-critique`
  - `../../TODO_TUNNING_PARTY.md`
  - `../../finetune/README.md`

### R-015 — KiCad MCP roadmap v2+
- Status: **Deferred (post-stabilisation)**
- Blocking condition:
  - attendre la stabilisation complete de la pile MCP supportee et la validation du runtime canonique sur hote et conteneur
- References:
  - `REMEDIATION_BACKLOG_2026-03-07.md#r-015--kicad-mcp-roadmap-v2`
  - `../../../Kill_LIFE/specs/kicad_mcp_scope_spec.md`
  - `../../finetune/kicad_mcp_server/docs/ROADMAP.md`

## Next recommended step
Poursuivre avec `R-004`, puis finaliser `R-006` (probe GPU + validation live des MCP a secrets), et garder un point de controle sur `R-001` tant que le swap n'est pas revenu a une valeur de repos acceptable.

## Next after stabilization
Quand `J0` et `J7` sont sous controle, ouvrir `R-010` a `R-015` dans l'ordre:
`contrat multi-repo` -> `CI canonique` -> `surface hote` -> `Workflow Editor lot 2` -> `fine-tuning hors pipeline critique` -> `KiCad MCP v2+`.
