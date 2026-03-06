# Remediation Backlog — 2026-03-05

## Objectif
Transformer les findings de l’audit global en plan d’actions exécutable, priorisé et vérifiable.

## J0 (immédiat, 24h)

### R-001 — Corriger permissions root sur fichiers projet
- Priorité: **Critique opérationnelle**
- Statut au 2026-03-05: **Réalisé** (ownership normalisé sur `api/`, `web/` et `deploy/clickhouse/*`)
- Problème: build API échoue (`EACCES`) à cause de fichiers root-owned.
- Cibles:
  - `api/src/routes/ops.ts`
  - `web/src/api/ops.ts`
  - `api/dist/routes/ops.d.ts`
  - `api/dist/routes/ops.js`
  - `deploy/clickhouse/users.d/langfuse-user.xml` + dossiers parents
- Action:
  - normaliser ownership `clems:clems` sur chemins projet.
  - empêcher génération root (règle d’exécution npm/docker).
- Critères d’acceptation:
  1. `npm run build` dans `api/` retourne code 0.
  2. `find api web deploy -user root` ne retourne aucun fichier source.

### R-002 — Supprimer secrets faibles/hardcodés par défaut
- Priorité: **Haute sécurité**
- Statut au 2026-03-05: **Réalisé** (y compris cleanup legacy `deploy/clickhouse/users.d/langfuse-user.xml`)
- Problème: `changeme`, `miniosecret`, mots de passe statiques.
- Cibles:
  - `.env.example`
  - `scripts/modules/langfuse.sh`
  - `scripts/modules/dify.sh`
  - `scripts/modules/n8n.sh`
  - `scripts/modules/postgres.sh`
  - `deploy/clickhouse/users.d/langfuse-user.xml`
- Action:
  - remplacer defaults faibles par variables obligatoires ou génération aléatoire.
  - documenter procédure de rotation.
- Critères d’acceptation:
  1. `rg -n "changeme|miniosecret" scripts modules deploy .env.example` ne retourne rien de hardcodé exploitable.
  2. démarrage stack OK avec secrets injectés.

### R-003 — Corriger runbook backup/restore
- Priorité: **Haute continuité**
- Statut au 2026-03-05: **Réalisé** (scripts ajoutés + backup/restore vérifiés)
- Problème: runbook référence scripts absents dans ce repo.
- Cibles:
  - `docs/RUNBOOK_VM_OPS.md`
  - `scripts/` (ajout scripts manquants ou références réelles)
- Action:
  - soit versionner scripts backup/restore dans ce repo,
  - soit réécrire docs vers emplacement source réel + prérequis exacts.
- Critères d’acceptation:
  1. chaque commande du runbook backup/restore est exécutable telle quelle.
  2. procédure restore validée sur dump de test.

## J7 (1 semaine)

### R-004 — Mettre en place CI minimale obligatoire
- Priorité: **Haute qualité**
- Statut au 2026-03-05: **Implémenté** (`.github/workflows/ci.yml`) — validation complète attendue sur runner GitHub
- Cibles:
  - `.github/workflows/ci.yml` (ou équivalent plateforme)
- Pipeline minimal:
  1. `api`: `npm ci`, `npm run test`, `npm run build`
  2. `web`: `npm ci`, `npm run build`
  3. `core`: environnement Python reproductible + `pytest -q`
  4. validation compose: `docker compose config`
- Critères d’acceptation:
  1. pipeline bloquante sur PR.
  2. badge/trace CI disponible.

### R-005 — Compléter healthchecks applicatifs
- Priorité: **Moyenne-Haute**
- Problème: services applicatifs sans vérification de readiness.
- Cibles:
  - `docker-compose.yml`
  - `scripts/modules/*` générateurs compose
- Action:
  - ajouter healthcheck pour `core`, `api`, `litellm`, `n8n`, `dify-*`, `langfuse-*`, `qdrant`, `prometheus`, `grafana`.
  - ajuster `depends_on` sur `service_healthy` quand pertinent.
- Critères d’acceptation:
  1. `docker compose ps` affiche statuts health cohérents.
  2. reboot stack sans race condition fonctionnelle.

### R-006 — Traiter warning n8n task runner
- Priorité: **Moyenne**
- Action:
  - configurer n8n task runners en mode externe recommandé,
  - ou désactiver explicitement fonctionnalité interne non utilisée.
- Critères d’acceptation:
  1. warning absent des logs à froid.
  2. workflows n8n critiques exécutés correctement.

## J30 (durable / gouvernance)

### R-007 — Politique sécurité secrets et rotation
- Priorité: **Moyenne**
- Action:
  - intégrer secret manager (ou chiffrement sops),
  - définir rotation trimestrielle (Postgres, ClickHouse, MinIO, clés app).
- Critères d’acceptation:
  1. aucun secret sensible en clair dans repo.
  2. procédure rotation testée et documentée.

### R-008 — Réduction du drift et hygiène release
- Priorité: **Moyenne**
- Action:
  - nettoyer artefacts suivis (assets build) via pipeline dédiée.
  - conventions release/branch et checklist pré-déploiement.
- Critères d’acceptation:
  1. `git status` propre avant release.
  2. build reproductible sans modifications inattendues.

### R-009 — Audit réseau hôte complet
- Priorité: **Moyenne**
- Action:
  - inventorier services non-Mascarade sur ports `80/81/3389/3390`.
  - appliquer politiques firewall + segmentation.
- Critères d’acceptation:
  1. matrice ports/propriétaires validée.
  2. exposition non nécessaire supprimée.

## KPI de sortie
1. Builds: `api` et `web` verts, `core` tests exécutables.
2. Sécurité: 0 secret faible/hardcodé en defaults de prod.
3. Ops: runbook backup/restore testé de bout en bout.
4. Runtime: stack redémarre sans erreurs récurrentes dans logs de démarrage.
