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

### `crazy_life`

| ID | Tache | Owner |
| --- | --- | --- |
| `C-DA-016` | Ouvrir le lot frontend `bundle + lazy loading + tests` sans rouvrir le gateway | `ui-sequence-mapper` |

### `Kill_LIFE`

| ID | Tache | Owner |
| --- | --- | --- |
| `K-DA-020` | Isoler le blocage restant de `bash tools/test_python.sh --suite stable` autour des deltas MCP runtime hors lot | `mcp-runtime-analyst` |

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
- production du diagramme `crazy_life/docs/CRAZY_LANE_SEQUENCE_2026-03-14.md`
- fermeture de `C-DA-003` via le realignement du `README`, du plan local et des ancres publication/cartographie
- fermeture de `C-DA-004` via `docs/GATEWAY_HARDENING_2026-03-14.md`, `api/src/index.ts` et l'audit strict `bash scripts/tui/gateway_audit.sh audit --strict`
- revalidation locale `crazy_life`: `npm --prefix api test` puis `npm run build`
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
- fermeture de `K-DA-011` via la section automatique `Focus failures` dans `Kill_LIFE/tools/auto_check_ci_cd.py`
- fermeture de `K-DA-012` via la compaction des chemins absolus dans `Kill_LIFE/tools/auto_check_ci_cd.py`
- fermeture de `K-DA-013` via la reduction des signaux listeux dans `Kill_LIFE/tools/auto_check_ci_cd.py`
- fermeture de `K-DA-014` via le bloc `Artifact summary` dans `Kill_LIFE/tools/auto_check_ci_cd.py`
- revalidation locale `Kill_LIFE`: rendu Markdown evidence avec chemins repo-relatifs apres `tools/auto_check_ci_cd.py`
- revalidation locale `Kill_LIFE`: rendu Markdown evidence avec comptes d'artefacts courts apres `tools/auto_check_ci_cd.py`
- revalidation locale `Kill_LIFE`: rendu Markdown evidence avec synthese artefacts dediee apres `tools/auto_check_ci_cd.py`
- revalidation locale `Kill_LIFE`: rendu rouge verifie via `render_markdown_summary(report)` et rendu vert revalide via `tools/auto_check_ci_cd.py`
- fermeture de `K-DA-015` via l'exposition `required_files` / `missing` dans `Kill_LIFE/tools/auto_check_ci_cd.py`
- revalidation locale `Kill_LIFE`: `./.venv/bin/python -m unittest discover -s test -p test_auto_check_ci_cd.py` puis `KILL_LIFE_PIO_MODE=native ./.venv/bin/python tools/auto_check_ci_cd.py`
- fermeture de `K-DA-016` via la colonne `Drift` dans `Kill_LIFE/tools/auto_check_ci_cd.py`
- fermeture de `M-DA-008` via l'exposition UI de `routing_selected_by`, `routing_transport` et `routing_latency_ms` dans `web/src/pages/Logs.tsx` et `web/src/pages/Orchestrate.tsx`
- revalidation locale `mascarade`: `npm --prefix web run build` et `npm --prefix api run build`
- fermeture de `C-DA-005` via `crazy_life/docs/UPSTREAM_DEPENDENCY_LEDGER_2026-03-14.md`
- revalidation operateur `crazy_life`: `bash scripts/tui/gateway_audit.sh audit --strict`, lecture du report, puis purge `.ops/gateway-audit`
- fermeture de `C-DA-006` via `crazy_life/docs/PLAIN_PROXY_PRIORITY_2026-03-14.md`
- fermeture de `C-DA-007` via `crazy_life/api/src/index.ts`, `api/src/index.test.ts`, `scripts/tui/gateway_audit.sh` et `docs/OPS_PROXY_HARDENING_2026-03-14.md`
- revalidation locale `crazy_life/api`: `npm --prefix api run build` puis `npm --prefix api test`
- fermeture de `C-DA-008` via `crazy_life/api/src/index.ts`, `api/src/index.test.ts`, `scripts/tui/gateway_audit.sh` et `docs/CLUSTER_PROXY_HARDENING_2026-03-14.md`
- revalidation operateur `crazy_life`: `bash scripts/tui/gateway_audit.sh audit --strict`, lecture du report, puis purge `.ops/gateway-audit`
- fermeture de `C-DA-009` via `crazy_life/api/src/index.ts`, `api/src/index.test.ts`, `scripts/tui/gateway_audit.sh` et `docs/KNOWLEDGE_BASE_PROXY_HARDENING_2026-03-14.md`
- revalidation locale `crazy_life/api`: `npm --prefix api run build` puis `npm --prefix api test`
- fermeture de `C-DA-010` via `crazy_life/api/src/index.ts`, `api/src/index.test.ts`, `scripts/tui/gateway_audit.sh` et `docs/CAD_PROXY_HARDENING_2026-03-14.md`
- revalidation operateur `crazy_life`: `bash scripts/tui/gateway_audit.sh audit --strict`, lecture du report, puis purge `.ops/gateway-audit`
- fermeture de `C-DA-011` via `crazy_life/docs/NON_PROXY_DEBT_CLASSIFICATION_2026-03-14.md` et `scripts/tui/non_proxy_debt_audit.sh`
- revalidation operateur `crazy_life`: `bash scripts/tui/non_proxy_debt_audit.sh audit --strict`, lecture du report, puis purge `.ops/non-proxy-debt-audit`
- fermeture de `C-DA-012` via `crazy_life/docs/RUNTIME_SMOKE_2026-03-14.md` et la smoke live `KILL_LIFE_ROOT=/Users/electron/Kill_LIFE bash scripts/dev.sh up`
- revalidation operateur `crazy_life`: `curl http://localhost:3100/api/killlife/workflows` vert, `curl http://localhost:3100/health` en `502` bloque precisement par upstream `:3000`, `127.0.0.1:3100` invalide a cause d'un conflit local `com.docker`
- fermeture de `C-DA-013` via `crazy_life/api/src/index.ts`, `api/src/index.test.ts`, `scripts/tui/runtime_smoke.sh` et l'exposition additive `killlife_lane_ready` / `upstream_ready` sur `/health`
- revalidation operateur `crazy_life`: `bash scripts/tui/runtime_smoke.sh audit --yes`, lecture du report `localhost` vs `127.0.0.1`, puis purge `.ops/runtime-smoke`
- fermeture de `C-DA-014` via `crazy_life/scripts/tui/workflow_lane_smoke.sh`, `docs/WORKFLOW_LANE_SMOKE_2026-03-14.md` et l'ignorance Git de `Kill_LIFE/.crazy-life/`
- revalidation operateur `crazy_life`: `bash scripts/tui/workflow_lane_smoke.sh audit --yes`, lecture du report `list -> detail -> validate -> dry_run -> run status`, puis purge `.ops/workflow-lane-smoke`
- fermeture de `C-DA-015` via `crazy_life/docs/GITHUB_CI_STATUS_2026-03-14.md` et la lecture `gh` des runs `ci` / `deploy-pages`
- revalidation GitHub `crazy_life`: `gh run list --repo electron-rare/crazy_life --limit 10 --json databaseId,workflowName,status,conclusion,url`
- reduction de regression `M-DA-004` cote `mascarade/api`: fallback `X-Forwarded-Groups` supprime; groupes implicites interdits dans `api/src/routes/mcpIndustrial.ts`
- revalidation locale `mascarade/api`: `npm --prefix api run build` puis `npm --prefix api test`
- revalidation locale `mascarade/core`: `cd core && ./.venv/bin/python -m pytest -q`
- fermeture de `K-DA-017` via `Kill_LIFE/tools/auto_check_ci_cd.py`, `test/test_auto_check_ci_cd.py` et le recalcul des artefacts encore presents en cas de drift `summary ok`
- revalidation locale `Kill_LIFE`: `./.venv/bin/python -m unittest discover -s test -p test_auto_check_ci_cd.py` puis `KILL_LIFE_PIO_MODE=native ./.venv/bin/python tools/auto_check_ci_cd.py`
- fermeture de `K-DA-018` via `Kill_LIFE/tools/auto_check_ci_cd.py`, `test/test_auto_check_ci_cd.py` et la separation explicite `Source artifacts` / `Evidence files`
- revalidation locale `Kill_LIFE`: `docs/evidence/ci_cd_audit_summary.md` regenere avec les colonnes `Source`, `Evidence files`, `Missing evidence` et `Drift`
- fermeture de `K-DA-019` via la relecture complete `KILL_LIFE_PIO_MODE=native ./.venv/bin/python tools/auto_check_ci_cd.py` et la confirmation que la doc evidence ne necessitait pas d'ajustement supplementaire

## Test status snapshot

- `mascarade/api`: `npm --prefix api run build` vert et `npm --prefix api test` vert (`62/62`) apres correction `mcpIndustrial`
- `mascarade/core`: `./.venv/bin/python -m pytest -q` vert dans l'etat courant du worktree; les suites cibles `test_cluster.py` et `test_orchestrator.py` restent vertes
- `crazy_life`: `npm --prefix api run build` vert et `npm --prefix api test` vert (`82/82`) apres smoke health explicite et scripts TUI `runtime_smoke` / `workflow_lane_smoke`
- `Kill_LIFE`: evidence lane locale verte en mode `native-pio`; la suite `bash tools/test_python.sh --suite stable` reste bloquee par un delta local hors lot dans `tools/mcp_runtime_status.py`
- aucune pretention de "suite verte globale" n'est faite sans reprise lot-par-lot
