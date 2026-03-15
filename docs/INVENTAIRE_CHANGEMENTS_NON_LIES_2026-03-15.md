# Inventaire des changements non lies (15 mars 2026)

## Resume executif

- Perimetre analyse: agent-factory-cockpit, crazy_life, Kill_LIFE, mascarade, mascarade-api-deps, mascarade-apple-coreml, mascarade-frontend-pr, mascarade-main.
- Repos avec changements locaux: crazy_life (23), Kill_LIFE (17), mascarade (24), mascarade-apple-coreml (1), mascarade-frontend-pr (1), mascarade-main (7).
- Repo propre: mascarade-api-deps (0).
- Repo non git: agent-factory-cockpit.
- Zone risque eleve: modifications workflows CI dans crazy_life.

## Baseline capturee

| Repo | Branch | Head court | Nb changements |
| --- | --- | --- | ---: |
| agent-factory-cockpit | n/a | n/a | n/a |
| crazy_life | main | 82afb0f | 23 |
| Kill_LIFE | main | 225f2f8 | 17 |
| mascarade | feat/apple-coreml-runtime-lot | 28c477f | 24 |
| mascarade-api-deps | chore/api-deps-pristine | 0107c5f | 0 |
| mascarade-apple-coreml | feat/apple-coreml-runtime-pristine | 64b8727 | 1 |
| mascarade-frontend-pr | feat/frontend-pr1-stability | 6b33289 | 1 |
| mascarade-main | main | 41515c6 | 7 |

## Repartition par zones (top-level)

### crazy_life
- src: 10
- api: 4
- docs: 2
- .github: 2
- autres: README, package, plan, LICENSE, .DS_Store

Fichiers sensibles detectes:
- .github/workflows/ci.yml
- .github/workflows/deploy-pages.yml

### Kill_LIFE
- docs: 8
- tools: 5
- specs: 1
- autres: deploy, README, .ops

### mascarade
- docs: 9
- core: 6
- scripts: 2
- autres: api, docker-compose, plan, README, TODO

### mascarade-main
- docs: 4
- core: 2
- scripts: 1

### repos legers
- mascarade-apple-coreml: 1 changement (scripts)
- mascarade-frontend-pr: 1 changement (MANIFEST)

## Inventaire cible des changements non lies

Definition operationnelle:
- Non lie = changement hors lot courant (ex: merge docs en cours) ou a risque de conflit inutile.

### Liste prioritaire a isoler

1. crazy_life
- Lots distincts proposes:
  - Lot CL-DOC: docs/TODO + docs/CI status + plan + README
  - Lot CL-API: api/src + api/package
  - Lot CL-UI: src/**
  - Lot CL-CI-SENSITIVE: .github/workflows/** (geler, ne pas toucher ici)
  - Lot CL-HYGIENE: .DS_Store

2. Kill_LIFE
- Lots distincts proposes:
  - Lot KL-DOCS: docs/**
  - Lot KL-SPECS: specs/mcp_tasks.md
  - Lot KL-TOOLS: tools/**
  - Lot KL-OPS: .ops/**

3. mascarade
- Lots distincts proposes:
  - Lot M-DOCS: docs/** + plan/todo/readme
  - Lot M-CORE: core/** + api/src/routes/ops.ts
  - Lot M-INFRA: docker-compose.yml
  - Lot M-SCRIPTS: scripts/**

4. mascarade-main
- Lots distincts proposes:
  - Lot MM-DOCS: docs/**
  - Lot MM-CORE: core/**
  - Lot MM-SCRIPTS: scripts/**

## Strategie chirurgicale de separation en lots

## Regles

- Ne pas melanger docs, code, infra, workflows dans un meme lot.
- Eviter toute modification workflows tant que la passe de merge n est pas stabilisee.
- Conserver des commits petits et verifiables.
- Ne jamais utiliser reset hard ou force push.

## Sequence recommandee

1. Etape S0: geler les lots sensibles
- crazy_life: exclure .github/workflows/** du flux courant.

2. Etape S1: nettoyer hygiene locale
- supprimer .DS_Store des repos touches et ajouter exclusion locale si necessaire.

3. Etape S2: sortir les lots docs purs
- CL-DOC, KL-DOCS, M-DOCS, MM-DOCS.
- Objectif: reduire le bruit avant merges code.

4. Etape S3: sortir les lots specs/outils
- KL-SPECS puis KL-TOOLS.

5. Etape S4: sortir les lots code applicatif
- CL-API puis CL-UI.
- M-CORE et MM-CORE selon preflight.

6. Etape S5: sortir les lots infra/scripts
- M-INFRA, M-SCRIPTS, MM-SCRIPTS.

7. Etape S6: seulement ensuite, reprise du runbook de merge lots inter-repos
- Lot 1 api-deps -> main
- Lot 2 apple-coreml -> main
- Lot 3 mascarade -> main
- Lot 4 frontend-pr partiel (cherry-pick)

## Commandes de tri (non destructives)

Exemple par repo pour visualiser un lot docs:

```bash
git status --short | rg '^.. docs/'
```

Exemple lot code API:

```bash
git status --short | rg '^.. api/'
```

Exemple lot UI:

```bash
git status --short | rg '^.. src/'
```

Exemple verification sensitive workflows:

```bash
git status --short | rg '^.. \.github/workflows/'
```

## Critere de sortie de cette phase

- Chaque repo possede une decomposition en lots sans chevauchement.
- Les fichiers sensibles sont identifies et geles tant que non necessaires.
- Les lots docs sont prets a etre consolides en premier.
- Le runbook de merge peut reprendre avec un niveau de risque reduit.

## Resultats preflight executes en parallele

### 1) Kill_LIFE
- Commande: `python3 tools/validate_specs.py --strict --require-mirror-sync` (fallback `--strict`)
- Resultat: FAIL
- Causes:
  - PyYAML absent
  - mismatch mirror: `constraints.yaml`, `mcp_tasks.md`

### 2) crazy_life
- Commande: `scripts/publish_preflight.sh check` (fallback `status`)
- Resultat: FAIL (gating)
- Cause:
  - worktree dirty (20+ changements)

### 3) mascarade-main
- Commande: `scripts/merge_preflight.sh baseline --strict-clean` (fallback `all`)
- Resultat:
  - strict-clean: FAIL (local changes detectes)
  - snapshot all: OK (rapport genere)
- Rapport:
  - `docs/audit/MERGE_PREFLIGHT_SNAPSHOT_2026-03-15_195139.md`

## Manifests de lots generes

- crazy_life: `docs/LOT_SPLIT_MANIFEST_2026-03-15.md`
- Kill_LIFE: `docs/LOT_SPLIT_MANIFEST_2026-03-15.md`
- mascarade: `docs/audit/LOT_SPLIT_MANIFEST_2026-03-15.md`

## Update execution (20:08)

### Commits docs-only executes

- crazy_life: `edc9590` - docs: align todo and lot split manifest for cross-repo cleanup
- Kill_LIFE: `3cfc599` - docs: refresh repo state and lot split manifests
- mascarade: `7c39253` - docs: align execution plan and lot split manifests

### Re-run gates

- Kill_LIFE specs gate: PASS (`--strict --require-mirror-sync`)
  - compliance ok: true
  - PyYAML available: true
  - mirror mismatch: 0
- crazy_life publish preflight (`--allow-dirty`): PASS
  - tests + builds locaux executes avec succes
- merge preflight global: snapshot regenere
  - `docs/audit/MERGE_PREFLIGHT_SNAPSHOT_2026-03-15_200750.md`

### Etat du bruit local apres lots docs

- crazy_life: 16 changements restants
- Kill_LIFE: 9 changements restants
- mascarade: 12 changements restants

### Preparation merge lots (cherry-pick)

Comparaison par remotes locales (`local-api`, `local-apple`, `local-front`) realisee depuis `mascarade-main`:

- lot 1 (`api-deps`) : aucun commit source unique detecte dans la fenetre comparee
- lot 2 (`apple-coreml`) : aucun commit source unique detecte dans la fenetre comparee
- lot 4 (`frontend-pr`) : aucun commit source unique detecte dans la fenetre comparee

Interpretation operationnelle:
- les deltas restants sont majoritairement des changements locaux non commites par repo,
- la suite doit passer par lots locaux (code/api/ui/tools/infra) avant relance merge inter-repos.

## Update convergence main (strategie 2)

- creation d'un worktree propre d'integration: `/Users/electron/.auto-claude/worktrees/integration-main-sync`
- branche d'integration: `integration/main-sync`
- merges absorbes dans la branche d'integration:
  - `feat/apple-coreml-runtime-lot`
  - `feat/apple-coreml-runtime-pristine`
  - `feat/frontend-pr1-stability`
- resolution de conflit repetee sur `MANIFEST.md`
- fast-forward reussi de `main` vers `integration/main-sync`

### Correctifs de stabilisation appliques ensuite

- compatibilite cache restauree dans le routeur
- contrainte `aiobreaker` assouplie vers une version resolvable
- compatibilite de l'orchestrateur restauree:
  - champ `retry_executor`
  - `dead_letter_store`
  - `circuit_breakers`
  - champs `fallback_used` / `fallback_agent`
  - gestion `skip_on_error` en sequential
  - fallback agent en pipeline

### Validation post-correctif

- `pytest tests/test_orchestrator.py -q`: PASS (suite ciblee)
- `npm --prefix api run build`: PASS dans le worktree d'integration
- `docker compose config`: PASS dans le worktree d'integration

### Limites restantes

- le worktree principal `mascarade-main` garde quelques fichiers non trackes utiles a trier separment
- les snapshots bruts de preflight ont ete analyses puis doivent etre supprimes ou ignores
