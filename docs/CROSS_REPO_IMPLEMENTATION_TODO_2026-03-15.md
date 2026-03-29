# Cross-Repo Implementation TODO (15 mars 2026)

Statut suite:
- type: `historical-reference`
- source active: `docs/EXECUTION_HUB.md`
- regle: les dependances cross-repo actives restent dans `docs/EXECUTION_HUB.md`; ne pas relancer ce plan tel quel

Objectif: executer la passe analyse/docs puis fusion main sans perte de donnees.

## Phase 1 - Docs/Specs/Plans (en cours)

- [x] Baseline git multi-repos capturee (branches, HEAD, dirty, worktrees)
- [x] Sync status central mis a jour avec decisions d'execution
- [x] Inventaire des changements non lies publie
- [x] TODO crazy_life aligne avec le programme cross-repo
- [x] REPO_STATE Kill_LIFE rafraichi
- [ ] Rafraichir plans/todos equivalents dans mascarade, mascarade-api-deps, mascarade-apple-coreml, mascarade-frontend-pr
- [x] Manifests de lots generes pour crazy_life, Kill_LIFE, mascarade
- [ ] Ajouter diagramme Mermaid de dependances multi-repos
- [ ] Ajouter diagramme Mermaid merge gates et sequence des lots
- [ ] Mettre a jour README centraux selon manifeste (mascarade-main, crazy_life, Kill_LIFE)

Reference inventaire:
- docs/INVENTAIRE_CHANGEMENTS_NON_LIES_2026-03-15.md

## Phase 2 - Merge preflight

- [x] Lancer preflight strict sur mascarade-main (strict fail, snapshot ok)
- [x] Lancer validation specs/compliance Kill_LIFE (fail: PyYAML + mirror mismatch)
- [x] Lancer preflight release crazy_life (fail: dirty worktree)
- [ ] Attacher logs utiles dans docs/audit et supprimer les logs temporaires non necessaires

## Phase 3 - Merge lots (sequentiel)

- [ ] Lot 1: api-deps -> main (cherry-picks thematiques)
- [ ] Lot 2: apple-coreml -> main (fallback + alerte forte)
- [ ] Lot 3: mascarade -> main (deltas references)
- [ ] Lot 4: frontend-pr -> main (merge partiel cherry-pick uniquement)
- [ ] Backport selectif main -> mascarade si derive detectee

## Phase 4 - Optimisation agressive post-merge

- [ ] Frontend: code splitting (CrazyLaneEditor, ComfyUI, Infrastructure)
- [ ] Frontend: tests de non-regression cibles
- [ ] Core/API: points chauds perf, robustesse failover, observabilite
- [ ] Finaliser un TUI d'analyse cross-repo et standardiser logs d'execution

## Phase 5 - QA et evidence pack

- [ ] E2E inter-repos: Crazy Lane -> API -> LLM -> resultat
- [ ] Evidence pack: commits, tests, logs, decisions
- [ ] Publication gate final
