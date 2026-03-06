# Runbook VM Ops

## Scope

This runbook covers install/update/rollback/backup for:
- `mascarade` stack (`/mascarade`)
- docker studio stack (`/opt/docker-studio-ai/tools/dev/docker-studio-ai`)

## Install / Bootstrap

Important:
- Ne pas lancer `npm`/`docker compose` en `sudo` dans ce repo.
- Utiliser un utilisateur membre du groupe `docker` pour éviter la génération de fichiers root-owned.

1. Create env files:
   - `cp /mascarade/.env.example /mascarade/.env`
   - `cp /opt/docker-studio-ai/tools/dev/docker-studio-ai/.env.example.project /opt/docker-studio-ai/tools/dev/docker-studio-ai/.env.local`
   - `cp /opt/docker-studio-ai/tools/dev/docker-studio-ai/.env.keys.example /opt/docker-studio-ai/tools/dev/docker-studio-ai/.env.keys.local`
2. Render runtime env for studio stack:
   - `cd /opt/docker-studio-ai/tools/dev/docker-studio-ai && scripts/render_runtime_env.sh`
3. Start containers:
   - `cd /mascarade && docker compose up -d`
   - `cd /opt/docker-studio-ai/tools/dev/docker-studio-ai && scripts/compose_env.sh up -d`
4. Enable local backup automation:
   - `cd /mascarade && scripts/install_backup_automation.sh`
5. Optional (docker studio stack only, if present):
   - `cd /opt/docker-studio-ai/tools/dev/docker-studio-ai && scripts/install_container_observability.sh`

## Update

1. `cd /mascarade && ./deploy/update.sh`
2. `cd /opt/docker-studio-ai/tools/dev/docker-studio-ai && scripts/render_runtime_env.sh`
3. `cd /opt/docker-studio-ai/tools/dev/docker-studio-ai && scripts/compose_env.sh pull`
4. `cd /opt/docker-studio-ai/tools/dev/docker-studio-ai && scripts/compose_env.sh up -d --remove-orphans`
5. Validate:
   - `docker ps -a`
   - `journalctl -u container-observability.service -n 50 --no-pager`

## Rollback

1. Identify previous image:
   - `docker image ls --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}'`
2. Pin image tag in compose/env.
3. Recreate targeted service:
   - `docker compose up -d --force-recreate <service>`
4. Validate health:
   - `docker ps -a --format 'table {{.Names}}\t{{.Status}}'`
   - `curl -fsS http://127.0.0.1:8100/health`

## Backup

PostgreSQL (`/mascarade`):
- Manual backup: `cd /mascarade && scripts/pg_backup.sh`
- Verify backup: `cd /mascarade && scripts/pg_restore_verify.sh --backup-file /path/to/backup.dump`
- Retention: `cd /mascarade && scripts/pg_backup_retention.sh --days 14`

Automation:
- Install cron jobs: `cd /mascarade && scripts/install_backup_automation.sh`
- Check cron: `crontab -l | grep mascarade-pg-backup`

## Alerting / Logs

- Container alerts:
  - `journalctl -u container-observability.service -f`
  - `tail -f /var/log/container-observability-alerts.log`
- Stack logs:
  - `cd /mascarade && docker compose logs -f --tail 100`
  - `cd /opt/docker-studio-ai/tools/dev/docker-studio-ai && scripts/compose_env.sh logs -f --tail 100`
