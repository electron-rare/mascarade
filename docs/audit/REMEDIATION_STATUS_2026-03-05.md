# Remediation Status — 2026-03-05

## Scope
Execution status of J0 actions from `REMEDIATION_BACKLOG_2026-03-05.md`.

## Global Status (2026-03-05 17:30 CET)
- Runtime: **18/18 services running**, infra healthchecks green pour les composants infra actifs a cette date, dont ClickHouse/MinIO/Postgres/Redis/Ollama et l'ancienne interface chat locale.
- J0: **3 done, 0 partial**.
- Primary residual risk moved to J7/J30 backlog (CI, healthchecks applicatifs, n8n task runner warning).

## J0 Detail

### R-001 — Permissions root sur fichiers projet
- Status: **Done**
- Done:
  - `api/src/routes/ops.ts` and `web/src/api/ops.ts` recreated with user ownership.
  - root-owned `api/dist/routes/ops.*` removed.
  - legacy `deploy/clickhouse/*` ownership repaired (`clems:clems`).
  - `api` build now passes.
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-05/j0_validation_2026-03-05T1513+0100.txt`

### R-002 — Secrets faibles/hardcodés
- Status: **Done**
- Done:
  - Weak defaults removed in `.env.example`.
  - Random secret generation added in compose/module scripts.
  - Langfuse/ClickHouse/MinIO credentials now read from env vars.
  - Runtime secrets rotated (`POSTGRES_PASSWORD`, `CLICKHOUSE_PASSWORD`, `MINIO_ROOT_PASSWORD`).
- Additional cleanup:
  - legacy file `deploy/clickhouse/users.d/langfuse-user.xml` aligned to `password from_env`.
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-05/j0_validation_2026-03-05T1513+0100.txt`

### R-003 — Runbook backup/restore
- Status: **Done**
- Done:
  - Added scripts: `pg_backup.sh`, `pg_restore_verify.sh`, `pg_backup_retention.sh`, `install_backup_automation.sh`.
  - Updated `RUNBOOK_VM_OPS.md` to reference local scripts and non-sudo usage.
  - Executed real backup and restore verification against running PostgreSQL container.
- Evidence:
  - `AUDIT_EVIDENCE_2026-03-05/j0_validation_2026-03-05T1513+0100.txt`

## Next Recommended Step
- R-004 is now implemented in `.github/workflows/ci.yml`; confirm first green run on GitHub runner.
- Continue with J7: app healthchecks and n8n task-runner hardening.
