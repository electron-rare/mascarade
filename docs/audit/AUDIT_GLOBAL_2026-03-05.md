# Audit Global Mascarade — 2026-03-05

## Résumé Exécutif
Audit 360 non intrusif réalisé sur la stack Mascarade (infra Docker, sécurité, résilience ops, qualité build/test, observabilité, performance légère).

Constat global:
- Runtime actuel stable: **18/18 services en `running`**, plusieurs services critiques `healthy`.
- Durcissement infra déjà en place: images runtime majoritairement verrouillées par digest, dépendances Compose conditionnelles, healthchecks partiels.
- Risques majeurs restants après J0: chaîne qualité incomplète (core tests indisponibles localement), healthchecks applicatifs partiels, warning n8n task runner.

Niveau de risque global: **Moyen** (runtime stable, mais actions J7/J30 nécessaires pour production stricte).

## Addendum Post-Remediation (2026-03-05 17:30 CET)
- Les actions J0 ont été implémentées et validées.
- Statut consolidé:
  - `R-001` permissions: **corrigé** (ownership normalisé sur chemins projet audités).
  - `R-002` secrets faibles: **corrigé** (cleanup legacy inclus).
  - `R-003` backup/runbook: **corrigé et vérifié** (backup + restore check exécutés).
  - `R-004` CI minimale: **implémentée** (`.github/workflows/ci.yml`, run GitHub à confirmer).
- Références:
  - `docs/audit/REMEDIATION_STATUS_2026-03-05.md`
  - `docs/audit/AUDIT_EVIDENCE_2026-03-05/j0_validation_2026-03-05T1513+0100.txt`

## Portée et Méthode
- Audit non intrusif, sans stress test.
- Collecte de preuves runtime/config/code sous `docs/audit/AUDIT_EVIDENCE_2026-03-05/`.
- Validation par inspection statique + commandes d’état + builds/tests non destructifs.

## Interfaces Publiques
- Aucune rupture d’API fonctionnelle validée dans cet audit.
- Les changements recommandés concernent surtout:
  - contrats de configuration (`.env`/secrets),
  - durcissement Compose (healthchecks/readiness),
  - outillage qualité/CI et runbook opérationnel.

## Points Positifs
1. Stack opérationnelle: services actifs et stables.
   - Preuve: `docs/audit/AUDIT_EVIDENCE_2026-03-05/docker_compose_ps.txt`
2. Verrouillage images en digest actif au runtime.
   - Preuve: `docs/audit/AUDIT_EVIDENCE_2026-03-05/docker_images_runtime_digests.txt`
3. Exposition réseau compose majoritairement en `127.0.0.1`.
   - Preuve: `docs/audit/AUDIT_EVIDENCE_2026-03-05/docker_compose_ps.txt`, `compose_non_localhost_ports_scan.txt`
4. Healthchecks présents pour services infra clés (clickhouse, postgres, redis, minio, ollama).
   - Preuve: `compose_healthchecks.txt`

## Findings Priorisés
Note: cette section décrit le snapshot initial de l’audit; le statut de correction courant est documenté dans l’addendum post-remediation et `REMEDIATION_STATUS_2026-03-05.md`.

### 1) Secrets faibles / hardcodés dans la logique de déploiement
- Sévérité: **Haute**
- Impact: fuite de credentials ou compromission latérale facilitée en cas d’exposition.
- Détails:
  - `POSTGRES_PASSWORD` par défaut `changeme`.
  - `miniosecret`, `langfuse`, `clickhouse` présents en clair dans modules/config.
  - mot de passe ClickHouse statique dans XML utilisateur.
- Preuves:
  - `secrets_pattern_scan.txt`
  - `deploy/clickhouse/users.d/langfuse-user.xml`
- Recommandation: supprimer défauts faibles, générer secrets forts à l’initialisation, externaliser secrets (vault/sops/env chiffré).

### 2) Build API cassable à cause de permissions root sur fichiers projet
- Sévérité: **Haute**
- Impact: blocage CI/CD et release locale (`npm run build` échoue).
- Détails:
  - erreurs `TS5033 EACCES` sur `api/dist/routes/ops.*`.
  - fichiers source projet root-owned (`api/src/routes/ops.ts`, `web/src/api/ops.ts`).
- Preuves:
  - `api_build.txt`
  - `root_owned_project_paths.txt`
- Recommandation: normaliser ownership repo (`clems:clems`) sur chemins projet + garde-fou CI.

### 3) Procédures backup/restore documentées mais scripts absents
- Sévérité: **Haute**
- Impact: risque de fausse confiance et RPO/RTO non garantis.
- Détails:
  - `RUNBOOK_VM_OPS.md` référence des scripts non présents dans ce repo.
- Preuves:
  - `docs_ops_refs.txt`
  - `backup_scripts_presence.txt`
- Recommandation: aligner runbook au repo réel ou intégrer scripts manquants versionnés.

### 4) Chaîne qualité incomplète côté Core
- Sévérité: **Moyenne-Haute**
- Impact: régressions non détectées sur composant central Python.
- Détails:
  - `pytest` indisponible dans l’environnement d’exécution audit.
  - absence de workflow CI repo (`.github/workflows`).
- Preuves:
  - `core_pytest_q.txt`
  - `ci_workflows_presence.txt`
- Recommandation: pipeline CI minimal obligatoire (lint/test/build) avec environnement reproductible.

### 5) Couverture healthcheck incomplète côté services applicatifs
- Sévérité: **Moyenne**
- Impact: démarrage “vert” possible sans réelle disponibilité applicative.
- Détails:
  - seulement 5 services avec healthcheck explicite.
- Preuves:
  - `compose_healthchecks.txt`
  - `compose_dep_conditions.txt`
- Recommandation: ajouter healthchecks pour `core`, `api`, `litellm`, `n8n`, `dify-*`, `langfuse-*`, `qdrant`, `prometheus`, `grafana`.

### 6) Bruit opérationnel n8n (task runner Python interne)
- Sévérité: **Moyenne**
- Impact: confusion opérationnelle / mode non recommandé pour prod.
- Détails:
  - warning explicite n8n: Python task runner interne indisponible.
- Preuve:
  - `logs_key_signals.txt`
- Recommandation: configurer mode externe task runner n8n ou valider explicitement non-usage.

### 7) Drift important du workspace
- Sévérité: **Moyenne**
- Impact: risque de déploiement non maîtrisé, difficulté d’audit continu.
- Détails:
  - volume élevé de modifications non commitées et artefacts générés.
- Preuves:
  - `git_status_short.txt`
  - `git_diff_stat.txt`
- Recommandation: politique branches/PR stricte + nettoyage artefacts build suivis.

### 8) Exposition réseau hôte hors stack Mascarade
- Sévérité: **Moyenne**
- Impact: surface d’attaque globale VM supérieure au périmètre applicatif.
- Détails:
  - écoute sur `22`, `80`, `81`, `3389`, `3390` visibles au niveau hôte.
- Preuve:
  - `host_listen_ports.txt`
- Recommandation: inventorier propriétaires de ports et appliquer filtrage/firewall explicite.

## État Runtime et Performance (non intrusif)
- Consommation notable:
  - `mascarade-open-webui` ~642 MiB
  - `mascarade-langfuse` ~479 MiB
  - `mascarade-clickhouse` CPU ~9.79%, I/O disque important
- Preuve:
  - `docker_stats_nostream.txt`

Conclusion perf:
- Pas de saturation globale observée au snapshot, mais ClickHouse reste le principal consommateur CPU/IO attendu.

## Limites de l’audit
1. Probes HTTP host (`host_http_probes.txt`) exécutés depuis environnement sandboxé; non conclusifs sur disponibilité externe réelle.
2. Audit sécurité dépendances (CVE) non exhaustif (pas de scan SCA complet exécuté).
3. Pas de test de charge volontaire (contrainte non intrusive).

## Plan correctif recommandé
Voir backlog exécutable détaillé:
- `docs/audit/REMEDIATION_BACKLOG_2026-03-05.md`
