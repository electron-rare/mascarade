# Runbook VM Ops

## Scope

This runbook covers the current Mascarade stack only:
- repo path: `/mascarade`
- services started by `./setup` and `docker compose`
- local `ops-console` served from this repo

Legacy `docker-studio-ai` material is migration-only and is not part of the standard install path anymore. Historical notes remain under `docs/migration/`.

## Install / Bootstrap

Important:
- Do not run `npm` or `docker compose` with `sudo` inside this repo.
- Use a user that belongs to the `docker` group.
- Keep `.env` owned by that same user.

1. Create the env file:
   - `cd /mascarade`
   - `cp .env.example .env`
2. Fill at least:
   - `MASCARADE_API_KEY`
   - provider keys you actually use
   - optional `COMFYUI_URL`, `NOTION_API_KEY`
3. Start the standard stack:
   - `cd /mascarade && ./setup --with core,api,ops-console --yes`
4. Start with AudioCraft too, if needed:
   - `cd /mascarade && ./setup --with core,api,ops-console,generate-audio --yes`
5. Optional real audio smoke test:
   - `cd /mascarade && ./setup --with core,api,ops-console,generate-audio --smoke-generate-audio --yes`

## Health Validation

Core:
- `curl -fsS http://127.0.0.1:8100/health`

API:
- `curl -fsS http://127.0.0.1:3100/health`

Ops Console:
- `curl -fsS http://127.0.0.1/`

Generate Audio:
- `curl -fsS http://127.0.0.1:9000/health | python3 -m json.tool`
- `cd /mascarade && bash scripts/smoke_generate_audio.sh --url http://127.0.0.1:9000`

Notes for `generate-audio`:
- `runtime_ready=true` means the runtime deps are importable.
- `model_loaded=false` at boot is normal.
- the real `POST /generate` smoke test is opt-in because first model load may take time.

## Update

1. `cd /mascarade`
2. `git pull --ff-only`
3. `./deploy/update.sh`
4. Validate:
   - `docker compose ps`
   - `curl -fsS http://127.0.0.1:8100/health`
   - `curl -fsS http://127.0.0.1:3100/health`

If `generate-audio` is deployed:
- `bash scripts/smoke_generate_audio.sh --url http://127.0.0.1:9000`

## Rollback

1. List candidate images:
   - `docker image ls --format 'table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}'`
2. Pin the target image tag or digest in `.env` / compose inputs.
3. Recreate the impacted service:
   - `cd /mascarade && docker compose up -d --force-recreate <service>`
4. Validate health:
   - `cd /mascarade && docker compose ps`
   - `curl -fsS http://127.0.0.1:8100/health`

## Backup

PostgreSQL:
- manual backup: `cd /mascarade && scripts/pg_backup.sh`
- verify backup: `cd /mascarade && scripts/pg_restore_verify.sh --backup-file /path/to/backup.dump`
- retention: `cd /mascarade && scripts/pg_backup_retention.sh --days 14`

Automation:
- install cron jobs: `cd /mascarade && scripts/install_backup_automation.sh`
- check cron: `crontab -l | grep mascarade-pg-backup`

## Logs / Operations

Stack logs:
- `cd /mascarade && docker compose logs -f --tail 100`

Single service logs:
- `cd /mascarade && docker compose logs -f --tail 100 core`
- `cd /mascarade && docker compose logs -f --tail 100 api`
- `cd /mascarade && docker compose logs -f --tail 100 generate-audio`

Status:
- `cd /mascarade && docker compose ps`
- `cd /mascarade && docker stats --no-stream`

## Legacy Note

If a machine still has `/opt/docker-studio-ai`, treat it as a separate migrated stack. Do not use it as a prerequisite for installing or updating Mascarade. Any compatibility procedures tied to that old stack live under `docs/migration/`.
