# Runbook — Control Plane TUI (2026-03-21)

Runbook court pour les scripts d’exploitation `control-plane`.

## Scripts concernés

- `scripts/deploy_control_plane.sh`
- `scripts/monitor.sh`
- `scripts/log_manager.sh`

## Contrat réel

### Déploiement

```bash
bash scripts/deploy_control_plane.sh --help
bash scripts/deploy_control_plane.sh photon
bash scripts/deploy_control_plane.sh kxkm
bash scripts/deploy_control_plane.sh tower
```

Pré-requis distants:
- `ssh`
- `rsync`
- `systemd`
- `node`
- droits `sudo -n` sur `kxkm` et `tower`

Sécurité:
- le script refuse maintenant de déployer des env files contenant des placeholders comme `change-me`
- override explicite possible via `--allow-example-env`

### Monitoring

```bash
bash scripts/monitor.sh --help
bash scripts/monitor.sh dashboard
bash scripts/monitor.sh nodes
bash scripts/monitor.sh providers
bash scripts/monitor.sh events
```

Routes attendues:
- `/api/cluster/state`
- `/api/cluster/events`
- `/api/v2/llm-providers`
- `/metrics`

### Gestion des logs

```bash
bash scripts/log_manager.sh --help
bash scripts/log_manager.sh list
bash scripts/log_manager.sh summary
bash scripts/log_manager.sh events
bash scripts/log_manager.sh journal
bash scripts/log_manager.sh --service mascarade-node-agent.service journal
bash scripts/log_manager.sh --file api/logs/control-plane.log tail
```

Notes:
- les services `systemd` du control-plane écrivent dans `journald`; `journal` est donc la source primaire sur `photon`, `kxkm` et `tower`
- les fichiers sous `api/logs` restent utiles pour des logs applicatifs locaux si activés par ailleurs
- `summary` streame maintenant la lecture au lieu de charger tout le fichier
- `latest_log_file` choisit le fichier le plus récent par `mtime`
- `delete` refuse les chemins hors de `LOG_DIR`

Exemples multi-machine:

```bash
ssh root@192.168.0.119 'cd /opt/mascarade/api && bash scripts/log_manager.sh --service mascarade-control-plane.service journal'
ssh kxkm@kxkm-ai 'cd /opt/mascarade/api && bash scripts/log_manager.sh --service mascarade-node-worker.service journal'
ssh clems@192.168.0.120 'cd /opt/mascarade/api && bash scripts/log_manager.sh --service mascarade-node-agent.service journal'
```

## Vérification minimale

```bash
bash -n scripts/deploy_control_plane.sh scripts/log_manager.sh scripts/monitor.sh scripts/lib/control_plane_cli.sh
bash scripts/deploy_control_plane.sh --help
bash scripts/log_manager.sh --help
bash scripts/monitor.sh --help
```

## Limites connues

- `cluster/events` est actuellement une façade sur les traces récentes, pas un bus d’événements dédié.
- `cluster/state` agrège l’identité cluster, les peers et le scheduler; ce n’est pas encore un inventaire exhaustif de capacité matérielle réelle.
- le package `api` échoue encore au `tsc` global sur le `node-engine` front/TSX, indépendamment des routes control-plane.
- `monitor.sh` observe uniquement le control-plane central; les logs runtime des nœuds restent à consulter localement ou via SSH.
