# Migration Machine Baseline

Ce document explique comment exporter un snapshot machine exploitable pour une migration.

## Objectif

Capturer dans le repo un etat operationnel de la machine:
- inventaire systeme (CPU, RAM, disque, services, erreurs),
- inventaire Docker (containers, stats, volumes, restarts),
- etat reseau (IPs, ports),
- inventaire skills (global + liens locaux),
- environnements redacts (sans secrets).

## Commande

Depuis la racine du repo:

```bash
bash scripts/export_machine_migration_bundle.sh
```

Optionnellement, forcer un dossier de sortie:

```bash
bash scripts/export_machine_migration_bundle.sh docs/migration/snapshots/manual-YYYYMMDD-HHMMSS
```

## Sortie

- Les snapshots sont ecrits sous `docs/migration/snapshots/<timestamp>/`.
- Le dernier snapshot est reference dans:
  - `docs/migration/LATEST_SNAPSHOT_PATH.txt`

## Redaction

Les fichiers `.env` exportes sont redacts automatiquement pour les cles sensibles:
- `*PASSWORD*`, `*PASS*`, `*TOKEN*`, `*SECRET*`, `*KEY*`, `*PRIVATE*`, `*CREDENTIAL*`.

## Notes

- Le script ne stoppe aucun service.
- Il peut necessiter des droits suffisants pour lire les infos systeme/docker.
- Les snapshots servent de baseline de migration et d'audit post-migration.
