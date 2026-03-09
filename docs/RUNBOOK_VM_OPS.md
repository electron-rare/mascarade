# Runbook VM Ops

## Scope

This runbook covers the current Mascarade stack only:
- repo path: `/mascarade`
- services started by `./setup` and `docker compose`
- local `ops-console` served from this repo

Legacy `docker-studio-ai` material is migration-only and is not part of the standard install path anymore. Historical notes remain under `docs/migration/`.

Machine portability notes, Docker/GPU fallbacks, and host-specific findings are
tracked in `docs/PORTAGE_MASCARADE.md`.

## Install / Bootstrap

Important:
- Do not run `npm` or `docker compose` with `sudo` inside this repo.
- Use a user that belongs to the `docker` group.
- Keep `.env` owned by that same user.
- If the host has an NVIDIA GPU, validate Docker GPU access before expecting
  local `generate-audio` or `comfyui` to run in GPU mode.

1. Create the env file:
   - `cd /mascarade`
   - `cp .env.example .env`
2. Fill at least:
   - `MASCARADE_API_KEY`
   - provider keys you actually use
   - optional `COMFYUI_URL`, `NOTION_API_KEY`, `KILL_LIFE_GITHUB_TOKEN`
3. Start the standard stack:
   - `cd /mascarade && ./setup --with core,api,ops-console,ollama --yes`
4. Start with AudioCraft too, if needed:
   - `cd /mascarade && ./setup --with core,api,ops-console,generate-audio,ollama --yes`
5. Optional real audio smoke test:
   - `cd /mascarade && ./setup --with core,api,ops-console,generate-audio,ollama --smoke-generate-audio --yes`
6. If the host already has system Ollama models under `/usr/share/ollama/.ollama`:
   - keep `OLLAMA_PUBLISH_PORT=false`
   - set `OLLAMA_HOST_MODELS_DIR=/usr/share/ollama/.ollama`
   - this reuses the host model store without exposing `11434` on the host
   - `./setup` now defaults to this mode when it detects `11434` already in use

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

Cockpit:
- `http://<host>:3100/logs` pour la vue live des traces inter-agent et des incidents services
- `http://<host>:3100/metrics` pour la posture health/latency

Stack logs:
- `cd /mascarade && docker compose logs -f --tail 100`

Single service logs:
- `cd /mascarade && docker compose logs -f --tail 100 core`
- `cd /mascarade && docker compose logs -f --tail 100 api`
- `cd /mascarade && docker compose logs -f --tail 100 generate-audio`
- `cd /mascarade && docker compose logs -f --tail 100 ollama`

Status:
- `cd /mascarade && docker compose ps`
- `cd /mascarade && docker stats --no-stream`

Observability complementaire opt-in:
- `cd /mascarade && ./setup --with core,api,ops-console,loki,promtail,otel-collector --yes`
- Loki et Promtail sont scaffoldes pour l'historique, mais la vue cockpit actuelle s'appuie deja sur la trace native du core et le monitor gateway
- Validation OTLP -> Loki:
  - `cd /mascarade && bash scripts/smoke_otel_loki.sh`
  - `cd /mascarade && bash scripts/smoke_otel_loki.sh --json`
- Controle de cardinalite Loki:
  - `cd /mascarade && bash scripts/loki_cardinality_report.sh`
  - `cd /mascarade && bash scripts/loki_cardinality_report.sh --json`

Setup backups:
- generated setup backups now live under `./.tmp/setup-backups/`

## Legacy Note

If a machine still has `/opt/docker-studio-ai`, treat it as a separate migrated stack. Do not use it as a prerequisite for installing or updating Mascarade. Any compatibility procedures tied to that old stack live under `docs/migration/`.
