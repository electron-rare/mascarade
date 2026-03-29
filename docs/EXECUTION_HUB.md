# Execution Hub

## Mission courante

Stabiliser `mascarade` sur `photon-machine`, garder les TODOs et runbooks aligns sur l'etat reel de chaque machine utile, puis enchainer vers les backlogs canoniques `crazy_life` et `kill_life` via un pilotage scope-aware plutot qu'un backlog implicite mono-machine.

## Repos et roles

| Repo | Role | Backlog canonique |
| --- | --- | --- |
| `mascarade` | Repo runtime/ops de cette machine et hub d'execution multi-repo | `docs/EXECUTION_HUB.md`, `TODO_VM.md` |
| `crazy_life` | Repo canonique web/devops et release du cockpit `Crazy Lane` | `/mascarade/opt/repos/crazy_life/plan.md` |
| `kill_life` | Source de verite workflows/MCP/CAD/runtime embarque | `/mascarade/opt/repos/kill_life/specs/mcp_tasks.md` |

## Sources actives

### Mascarade local/runtime

- `mascarade/docs/EXECUTION_HUB.md` est la source de truth humaine du backlog local et des bridges cross-repo.
- `mascarade/TODO_VM.md` reste le backlog machine actif pour `photon-machine`.
- `mascarade/docs/TODO_PLAN_REGISTRY.yaml` enregistre le corpus TODO/plan canonise et ses roles.
- `mascarade/docs/TODO_CROSS_REFERENCE.md` est le rapport derive de validation, a regenerer via `scripts/validate_todo_plan_suite.py`.
- `mascarade/docs/PERSONAL_STACK_MACHINE.md` et `mascarade/docs/MACHINE_PROFILES.json` restent des references operateur actives.

### Bridge vers crazy_life

- `../crazy_life/plan.md` reste le backlog cockpit/release canonique.

### Bridge vers Kill_LIFE

- `../Kill_LIFE/specs/mcp_tasks.md` reste le backlog MCP/CAD/runtime canonique.
- `kill_life/docs/plans/15_plan_mcp_stack.md` et `kill_life/docs/plans/15_todo_mcp_stack.md` sont explicitement deprecies.

### References historiques ou livrees

- `mascarade/TODO_COCKPIT_OPS.md`, `mascarade/TODO_IMPLEMENTE.md`, `mascarade/TODO_TUNNING_PARTY.md` et `mascarade/plan.md` sont conserves comme references, pas comme backlogs actifs.

## File d'execution

| ID | Repo canonique | Titre | Statut | Portee | Depend | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| `M-001` | `mascarade` | Recaler le hub et les TODOs actifs sur l'etat reel | `DONE` | `machine:photon-machine` | `-` | Lecture croisee des docs runtime et backlog |
| `M-002` | `mascarade` | Empecher un `.env` runtime avec `MASCARADE_API_KEY` vide | `DONE` | `machine:photon-machine` | `M-001` | `bash -n`, smoke shell cible |
| `M-003` | `mascarade` | Clarifier overlays machine et runbooks operateur | `DONE` | `machine:photon-machine` | `M-001` | Lecture croisee `README` + runbook + exemples |
| `M-004` | `mascarade` | Rendre le profil observabilite coherent et safe par defaut | `DONE` | `machine:photon-machine` | `M-001` | `bash -n`, harness shell de generation `.env` |
| `M-005` | `mascarade` | Activer et valider la stack observabilite live sur `photon-machine` | `DONE` | `machine:photon-machine` | `M-004` | `scripts/smoke_otel_loki.sh`, `scripts/loki_cardinality_report.sh` |
| `M-006` | `mascarade` | Ajouter des scripts d'enchainement automatique du hub | `DONE` | `global` | `M-005` | `scripts/execution_hub.py`, `scripts/next_useful_lot.sh`, `scripts/chain_next_lot.sh` |
| `M-007` | `mascarade` | Etendre le rapport de cardinalite aux flux OTLP | `DONE` | `machine:photon-machine` | `M-005` | bash scripts/loki_cardinality_report.sh --json doit inclure les streams OTLP enrichis |
| `M-008` | `mascarade` | Documenter explicitement le non-choix de backend OTel durable sur photon-machine | `DONE` | `machine:photon-machine` | `M-007` | Lecture croisee docs observabilite + runbook + deploy/otel-collector/config.yaml |
| `M-009` | `mascarade` | Verifier la cardinalite Loki sur trafic reel non-smoke | `BLOCKED` | `machine:photon-machine` | `M-008` | bash scripts/loki_cardinality_report.sh --json doit montrer des labels enrichis sur du trafic non-smoke ou enregistrer un blocage explicite |
| `M-010` | `mascarade` | Rendre le hub d'execution scope-aware pour le multi-machine | `DONE` | `global` | `M-006` | scripts/execution_hub.py context/next/list + wrappers --machine |
| `M-011` | `mascarade` | Ajouter une matrice de dispatch des prochains lots par machine | `DONE` | `global` | `M-010` | scripts/execution_hub.py matrix + scripts/machine_lot_matrix.sh |
| `M-012` | `mascarade` | Canoniser la suite TODO/plan et sa validation derivee | `DONE` | `global` | `M-011` | scripts/validate_todo_plan_suite.py + docs/TODO_PLAN_REGISTRY.yaml + docs/TODO_CROSS_REFERENCE.md |
| `C-001` | `crazy_life` | Resoudre la publication canonique qui echoue en `404` | `PENDING` | `cap:network-online` | `M-001` | Validation remote + `scripts/publish_preflight.sh` |
| `K-012` | `kill_life` | Rejouer la validation host-native KiCad | `PENDING` | `cap:kicad-host` | `-` | python3 tools/hw/kicad_host_mcp_smoke.py --json --quick |
| `K-014` | `kill_life` | Valider le mode live `nexar_api` | `PENDING` | `cap:nexar-live` | `-` | python3 tools/nexar_mcp_smoke.py --json --live |

## Lot en cours
Machine courante: `photon-machine`
Capacites: `dify-machine, docker-runtime, lan-ops, observability-local`

Aucun lot runnable detecte automatiquement.

Bloquants connus:
- `M-009` - Verifier la cardinalite Loki sur trafic reel non-smoke

## Prochains lots
Machine courante: `photon-machine`
Capacites: `dify-machine, docker-runtime, lan-ops, observability-local`

1. `M-009` - Verifier la cardinalite Loki sur trafic reel non-smoke (mascarade) [blocked]

## Bloquants

- `M-009` bloque sur `photon-machine`: la validation non-smoke via `/api/agents/orchestrate` requiert au moins un provider actif, et `GET /health` du core retourne actuellement `providers: []`.
- `C-001` demande une machine avec capacite `network-online` pour refaire la validation remote de `crazy_life`.
- `K-012` demande une machine avec capacite `kicad-host` pour rejouer `pcbnew` host-native.
- `K-014` demande une machine avec capacite `nexar-live` et un `NEXAR_TOKEN` reel pour sortir du mode demo.

## Hypotheses / decisions

- `mascarade` reste le point d'entree operateur de cette machine et porte le hub central.
- `ops-console` sur `:80` via le main compose est le chemin standard local; `edge-proxy` n'est plus la surface principale par defaut.
- `DIFY_MACHINE_HOST` reste la source unique des URLs Dify publiees.
- Un runtime `core` ou `api` ne doit plus sortir de `./setup` avec `MASCARADE_API_KEY` vide.
- Le hub central est maintenant filtre par `Portee`: `global`, `machine:<hostname>` ou `cap:<capability>`.
- Les questions utilisateur sont reservees aux secrets manquants, choix produit non derivables, actions destructives ou conflits de worktree non resolvables proprement.

## Journal d'execution

- `2026-03-09` - `M-001` termine. Hub central ajoute et TODOs actifs recales sur la VM reelle.
- `2026-03-09` - `M-002` termine. `write_env_file()` preserve ou genere `MASCARADE_API_KEY` pour eviter un runtime public involontaire.
- `2026-03-09` - `M-003` termine. `README`, runbook VM et exemples machine aligns sur le nouveau contrat.
- `2026-03-09` - `M-004` termine. Le profil observabilite devient coherent par defaut: binds loopback dedies et `OTEL_ENABLED=true` quand `otel-collector` est selectionne.
- `2026-03-09` - `K-012` probe sur `photon-machine`: statut `degraded`, bloque tant que `pcbnew` n'est pas importable sur l'hote.
- `2026-03-09` - `K-014` probe sur `photon-machine`: statut `degraded`, bloque tant que `NEXAR_TOKEN` manque et que le serveur reste en mode demo.
- `2026-03-09` - `C-001` verifie dans l'environnement courant: `git remote show origin` echoue faute de resolution DNS vers `github.com`.
- `2026-03-09` - M-005 termine. Les probes host 127.0.0.1:13133 et 127.0.0.1:3101 repondent hors sandbox, et le smoke OTLP vers Loki passe de bout en bout.
- `2026-03-09` - M-006 termine. Scripts de selection, refresh, journalisation et chaining ajoutes au repo.
- `2026-03-09` - M-010 termine. Le hub devient scope-aware pour le multi-machine via `Portee`, profils machine et wrappers `--machine`.
- `2026-03-09` - lot M-007 passe automatiquement a IN_PROGRESS via scripts/chain_next_lot.sh
- `2026-03-09` - M-007 termine. Le report Loki couvre maintenant par defaut les streams compose_project=mascarade et les flux OTLP etiquetes avec run_id, avec validation live sur photon-machine.
- `2026-03-09` - M-008 ajoute comme prochain lot utile mascarade apres la validation live du report de cardinalite.
- `2026-03-09` - lot M-008 passe automatiquement a IN_PROGRESS via scripts/chain_next_lot.sh
- `2026-03-09` - M-009 ajoute pour garder le prochain lot utile mascarade visible apres la clarification du mode debug OTel.
- `2026-03-09` - M-008 termine. La doc ops et la config du collector explicitent maintenant que photon-machine garde traces et metrics sur l'exporter debug tant qu'aucun backend durable n'est choisi.
- `2026-03-09` - lot M-009 passe automatiquement a IN_PROGRESS via scripts/chain_next_lot.sh
- `2026-03-09` - M-009 bloque sur photon-machine. La validation non-smoke via /api/agents/orchestrate requiert au moins un provider actif, et GET /health du core retourne actuellement providers=[].
- `2026-03-09` - M-011 ajoute pour rendre le dispatch multi-machine directement exploitable depuis les scripts.
- `2026-03-09` - M-011 passe en cours pour ajouter une matrice des prochains lots par machine.
- `2026-03-09` - M-011 termine. Une matrice de dispatch multi-machine est maintenant disponible avec profils logiques et prochain lot utile par machine.
- `2026-03-09` - M-011 termine. Une matrice de dispatch multi-machine est maintenant disponible avec profils logiques et prochain lot utile par machine.
- `2026-03-29` - `M-012` termine. Le registre `docs/TODO_PLAN_REGISTRY.yaml`, le validateur `scripts/validate_todo_plan_suite.py` et le rapport derive `docs/TODO_CROSS_REFERENCE.md` remplacent le suivi implicite du corpus TODO/plan.
- `2026-03-09` - stack personnelle legere automatisee. Les manifests `deploy/personal-seed/*.json` et les scripts `personal_stack_*` rejouent et verifient maintenant la wave 1 locale sans seed manuel.
