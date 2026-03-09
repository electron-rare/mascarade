# Runbook VM Ops

## Scope

This runbook covers the current Mascarade stack only:
- repo path: `/mascarade`
- services started by `./setup` and `docker compose`
- local `ops-console` served from this repo

Legacy `docker-studio-ai` material is migration-only and is not part of the standard install path anymore. Historical notes remain under `docs/migration/`.

Machine portability notes, Docker/GPU fallbacks, and host-specific findings are
tracked in `docs/PORTAGE_MASCARADE.md`.

Execution tracking lives in `docs/EXECUTION_HUB.md`.
Use `TODO_VM.md` for machine/runtime follow-up and `TODO_COCKPIT_OPS.md` for observability follow-up.
Multi-machine hub routing is described in `docs/MULTI_MACHINE_EXECUTION.md`.

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
   - for `photon-machine`, also copy `cp .env.machine.local.example .env.machine.local`
2. Fill at least:
   - provider keys you actually use
   - optional `COMFYUI_URL`, `NOTION_API_KEY`, `KILL_LIFE_GITHUB_TOKEN`
   - on `photon-machine`, also set `DIFY_SECRET_KEY` and shared Dify DB credentials in `.env.machine.local`
   - if `MASCARADE_API_KEY` is not set and `core` or `api` are selected, `./setup` now generates a strong value instead of leaving the runtime public
   - explicit `MASCARADE_API_KEY` remains preferred for operator-managed environments
3. Start the standard stack:
   - `cd /mascarade && ./setup --with core,api,ops-console,ollama --yes`
4. Start Dify on `photon-machine` with the dedicated machine compose:
   - `cd /mascarade && docker compose --env-file .env.machine.local -f deploy/dify.machine.yml config`
   - `cd /mascarade && docker compose --env-file .env.machine.local -f deploy/dify.machine.yml up -d`
5. Start with AudioCraft too, if needed:
   - `cd /mascarade && ./setup --with core,api,ops-console,generate-audio,ollama --yes`
6. Optional real audio smoke test:
   - `cd /mascarade && ./setup --with core,api,ops-console,generate-audio,ollama --smoke-generate-audio --yes`
7. If the host already has system Ollama models under `/usr/share/ollama/.ollama`:
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

Dify Web on `photon-machine`:
- `curl -fsS http://127.0.0.1:3500/ >/dev/null`

Dify API on `photon-machine`:
- `curl -fsS http://127.0.0.1:5001/health`

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
   - if Dify is deployed on `photon-machine`: `docker compose --env-file .env.machine.local -f deploy/dify.machine.yml ps`

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
- `OBSERVABILITY_BIND_HOST=127.0.0.1` reste la posture par defaut pour `loki`, `promtail`, `otel-collector`, `prometheus`, `grafana` et `ops-agent`
- si `otel-collector` est selectionne, `./setup` passe `OTEL_ENABLED=true` par defaut sauf override explicite
- sur `photon-machine`, `traces` et `metrics` restent volontairement sur l'exporter `debug`; seul le pipeline `logs` est branche vers Loki par defaut
- Validation OTLP -> Loki:
  - `cd /mascarade && bash scripts/smoke_otel_loki.sh`
  - `cd /mascarade && bash scripts/smoke_otel_loki.sh --json`
- Controle de cardinalite Loki:
  - `cd /mascarade && bash scripts/loki_cardinality_report.sh`
  - `cd /mascarade && bash scripts/loki_cardinality_report.sh --json`
  - le report couvre par defaut les streams Compose `mascarade` et les flux OTLP deja etiquetes avec `run_id`

Pilotage auto du hub:
- `cd /mascarade && scripts/current_machine_context.sh`
- `cd /mascarade && scripts/current_machine_context.sh --json`
- `cd /mascarade && scripts/next_useful_lot.sh --json`
- `cd /mascarade && scripts/machine_lot_matrix.sh`
- `cd /mascarade && scripts/machine_lot_matrix.sh --json`
- `cd /mascarade && scripts/chain_next_lot.sh`
- `cd /mascarade && scripts/chain_next_lot.sh --start --json`
- pour viser une autre machine declaree dans `docs/MACHINE_PROFILES.json`:
  - `cd /mascarade && scripts/next_useful_lot.sh --machine <nom> --json`
  - `cd /mascarade && scripts/chain_next_lot.sh --machine <nom> --start --json`
- pour voir tous les scopes sans filtrage machine:
  - `cd /mascarade && scripts/next_useful_lot.sh --all-scopes --json`

Setup backups:
- generated setup backups now live under `./.tmp/setup-backups/`

## Legacy Note

If a machine still has `/opt/docker-studio-ai`, treat it as a separate migrated stack. Do not use it as a prerequisite for installing or updating Mascarade. Any compatibility procedures tied to that old stack live under `docs/migration/`.
