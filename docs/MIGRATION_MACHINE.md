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
- Les decisions de portabilite du repo (fallback CPU/GPU, diagnostics Docker,
  ecarts machine/VM) sont documentees dans `docs/PORTAGE_MASCARADE.md`.

## Migration stack IA (LocalAI, KoboldCPP, AnythingLLM, SGLang, Mem0, Langfuse)

Le repo embarque un overlay compose et un requirements Python pour rejouer le setup IA:

- `deploy/migration/compose.tools.ai.yml`
- `deploy/migration/python-tools.requirements.txt`
- `scripts/apply_ai_tools_migration.sh`

Application sur une VM cible:

```bash
cd /mascarade
bash scripts/apply_ai_tools_migration.sh /home/cils/tools
```

Demarrage explicite des services lourds:

```bash
cd /home/cils/tools
docker compose -f docker-compose.yml -f docker-compose.ai.yml --profile heavy up -d localai koboldcpp anythingllm sglang
```

Sur machine legere, laisser ces services arretes par defaut (profil `heavy`).
