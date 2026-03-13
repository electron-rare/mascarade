# Multi-Repo Deep Analysis Program — 2026-03-11

## Scope

Repos pilotes:

| Repo | Role courant | Statut dans ce programme |
| --- | --- | --- |
| `mascarade` | Hub runtime/ops, orchestration agentique, bridge historique | hub central, outillage et baseline |
| `crazy_life` | Repo canonique web/devops du cockpit et de `Crazy Lane` | analyse doc + cartographie UI/API a produire |
| `Kill_LIFE` | Source de verite runtime, workflows, evidence, firmware, CAD, compliance | analyse fonctionnelle et diagrammes d'execution a produire |
| `kicad` | depot upstream de reference, pas repo produit du chantier | reference externe, hors campagne de refacto profonde |

Documents d'ancrage:

- `README.md`
- `docs/EXECUTION_HUB.md`
- `docs/audit/MULTI_REPO_BASELINE_2026-03-11.md`
- `../crazy_life/docs/REPO_CARTOGRAPHY_2026-03-07.md`

## Operating rules

- Travailler de facon chirurgicale: petits deltas, pas de re-ecriture large sans preuve.
- Utiliser des scripts TUI/logues quand l'action est recurrente ou operateur-facing.
- Ecrire les logs dans des fichiers temporaires, les lire, les resumer, puis les supprimer sauf demande explicite.
- Ne pas dupliquer les contrats de role: la cartographie repo reste la reference.
- Chaque repo doit finir avec un trio minimal: README a jour, diagrammes de sequence, carte fonctionnelle.

## Agents, sous-agents et competences

| Repo | Lead agent | Sous-agents | Competences / skills |
| --- | --- | --- | --- |
| `mascarade` | `runtime-architect` | `sequence-mapper`, `feature-cartographer`, `readme-curator`, `code-surgeon`, `test-auditor`, `open-source-scout` | `bash-cli-tui`, `playwright` |
| `crazy_life` | `cockpit-cartographer` | `ui-sequence-mapper`, `workflow-surface-analyst`, `release-readme-curator`, `api-contract-auditor` | `bash-cli-tui`, `playwright` |
| `Kill_LIFE` | `embedded-systems-auditor` | `mcp-runtime-analyst`, `firmware-doctor`, `compliance-cartographer`, `workflow-map-curator`, `readme-curator` | `bash-cli-tui`, `platformio-firmware-bootstrap`, `esp32-freenove-audit`, `esp32-runtime-debug` |

## Deliverables expected per repo

### `mascarade`

- diagramme de sequence `API -> core -> providers -> observability`
- carte fonctionnelle des surfaces `api`, `core`, `deploy`, `scripts`, `finetune`, `web`
- README aligne sur le manifeste et sur le contrat multi-repo
- correction des regressions rapides detectables par tests locaux

### `crazy_life`

- diagrammes de sequence pour `UI -> Hono API -> Kill_LIFE workflows`
- carte fonctionnelle des pages, lanes, modules de release et integration `api/public`
- README qui renvoie explicitement vers la cartographie repo et le plan actif

### `Kill_LIFE`

- diagrammes de sequence pour `spec -> workflow -> local action/github dispatch -> evidence pack`
- carte fonctionnelle des surfaces `agents`, `specs`, `workflows`, `tools`, `hardware`, `firmware`, `compliance`, `openclaw`
- README + docs/plans synchronises avec le contrat repo courant

## Plans actifs et prochaines taches

### `mascarade`

| ID | Tache | Owner |
| --- | --- | --- |
| `M-DA-001` | Maintenir le baseline multi-repo via `scripts/repo_deep_analysis_tui.sh` | `runtime-architect` |
| `M-DA-004` | Continuer la reduction des regressions `api` puis `core` par lots verifies | `code-surgeon` |
| `M-DA-008` | Consolider une lecture operateur plus synthétique des traces cluster/P2P | `sequence-mapper` |

### `crazy_life`

| ID | Tache | Owner |
| --- | --- | --- |
| `C-DA-002` | Ajouter un diagramme de sequence pour la lane workflow `Crazy Lane` | `ui-sequence-mapper` |
| `C-DA-003` | Rafraichir le README pour relier plan, publication et cartographie | `release-readme-curator` |
| `C-DA-004` | Verifier la couverture `api/public` et les limites du proxy upstream | `api-contract-auditor` |

### `Kill_LIFE`

| ID | Tache | Owner |
| --- | --- | --- |
| `K-DA-011` | Ajouter un focus automatique sur les lanes en echec dans le resume Markdown | `embedded-systems-auditor` |

## Actions documentees dans ce tour

- inventaire des repos Git locaux et des ancres README/plan/TODO/diagrammes
- creation du script TUI `scripts/repo_deep_analysis_tui.sh`
- creation du baseline `docs/audit/MULTI_REPO_BASELINE_2026-03-11.md`
- ajout de plans repo-locaux pour `crazy_life` et `Kill_LIFE`
- ajout des liens README vers les plans actifs
- correction ciblee d'une regression API dans `api/src/routes/mcpIndustrial.ts`
- production du diagramme de sequence `docs/API_CORE_PROVIDER_SEQUENCE_2026-03-11.md`
- production du diagramme `docs/CLUSTER_P2P_REMOTE_SEND_SEQUENCE_2026-03-11.md`
- production de la carte fonctionnelle `docs/MASCARADE_FEATURE_MAP_2026-03-11.md`
- correction ciblee du forwarding P2P `libp2p` dans `core/mascarade/cluster.py`
- ajout d'un test cible dans `core/tests/test_cluster.py`
- revalidation ciblee: `cd core && ./.venv/bin/python -m pytest -q tests/test_cluster.py`
- exposition de `routing_transport` et `routing_latency_ms` dans `AgentTraceBuffer` et l'orchestrateur
- revalidation ciblee: `cd core && ./.venv/bin/python -m pytest -q tests/test_orchestrator.py tests/test_cluster.py`
- exposition de `routing_selected_by` dans `AgentTraceBuffer` et l'orchestrateur
- production de la carte fonctionnelle `crazy_life/docs/CRAZY_LIFE_FEATURE_MAP_2026-03-11.md`
- reliaison du `README` et du plan `crazy_life` vers la nouvelle carte
- revalidation ciblee: `cd core && ./.venv/bin/python -m pytest -q tests/test_orchestrator.py`
- production de la carte fonctionnelle `Kill_LIFE/docs/KILL_LIFE_FEATURE_MAP_2026-03-11.md`
- reliaison du `README` et du plan `Kill_LIFE` vers la nouvelle carte
- production du diagramme `Kill_LIFE/docs/KILL_LIFE_WORKFLOW_LOCAL_SEQUENCE_2026-03-11.md`
- reliaison du `README` et du plan `Kill_LIFE` vers le diagramme `workflow local`
- production du diagramme `Kill_LIFE/docs/KILL_LIFE_WORKFLOW_GITHUB_SEQUENCE_2026-03-11.md`
- reliaison du `README` et du plan `Kill_LIFE` vers le diagramme `workflow github`
- synchronisation de la doc operateur `Kill_LIFE` (`docs/RUNBOOK.md`, `docs/index.md`, `docs/workflows/README.md`, `docs/AI_WORKFLOWS.md`, `docs/evidence/evidence_pack.md`) autour des sequences `local` et `github`
- fermeture de `K-DA-006` via l'alignement de `.github/workflows/evidence_pack.yml` sur `tools/auto_check_ci_cd.py` et `docs/evidence/*`
- ajout de la note d'audit `Kill_LIFE/docs/EVIDENCE_ALIGNMENT_2026-03-11.md`
- verification locale de la chaine evidence `Kill_LIFE`: `./.venv/bin/python tools/auto_check_ci_cd.py` avec sortie `linux` exploitable et `esp` partielle mais tracee
- fermeture de `K-DA-007` via la detection `native-pio` dans le venv repo-local et le durcissement anti-artefacts obsoletes dans `tools/collect_evidence.py`
- ajout du test cible `Kill_LIFE/test/test_firmware_evidence.py`
- revalidation locale `Kill_LIFE`: `KILL_LIFE_PIO_MODE=native ./.venv/bin/python tools/auto_check_ci_cd.py` vert sur `esp` + `linux`
- fermeture de `K-DA-008` via la mise en cache `pip` et `PlatformIO` dans `.github/workflows/evidence_pack.yml`
- ajout du verrou de version `Kill_LIFE/tools/compliance/requirements-platformio.txt`
- revalidation locale `Kill_LIFE`: `bash tools/bootstrap_python_env.sh --with-platformio` puis `KILL_LIFE_PIO_MODE=native ./.venv/bin/python tools/auto_check_ci_cd.py`
- fermeture de `K-DA-009` via la generation du GitHub Step Summary depuis `Kill_LIFE/tools/auto_check_ci_cd.py`
- ajout du test cible `Kill_LIFE/test/test_auto_check_ci_cd.py`
- revalidation locale `Kill_LIFE`: `GITHUB_STEP_SUMMARY=<tmp> KILL_LIFE_PIO_MODE=native ./.venv/bin/python tools/auto_check_ci_cd.py`
- fermeture de `K-DA-010` via le sidecar Markdown `Kill_LIFE/docs/evidence/ci_cd_audit_summary.md`
- revalidation locale `Kill_LIFE`: sidecar Markdown et Step Summary identiques apres `tools/auto_check_ci_cd.py`

## Test status snapshot

- `mascarade/api`: un echec local initial observe dans `src/routes/mcpIndustrial.test.ts` avant correctif
- `mascarade/core`: suite non verte dans l'etat actuel du worktree; plusieurs echecs relevent soit de regressions locales P2P/cluster, soit de limites sandbox sur le bind reseau
- `mascarade/core/tests/test_cluster.py` et `mascarade/core/tests/test_orchestrator.py`: verts sur le lot courant
- `Kill_LIFE`: evidence lane locale verte en mode `native-pio`; la suite `bash tools/test_python.sh --suite stable` reste bloquee par un delta local hors lot dans `tools/mcp_runtime_status.py`
- aucune pretention de "suite verte globale" n'est faite sans reprise lot-par-lot
