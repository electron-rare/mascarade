#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_CRON="${BACKUP_CRON:-1 0 * * *}"
RETENTION_CRON="${RETENTION_CRON:-11 0 * * *}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

BACKUP_MARKER="# mascarade-pg-backup"
RETENTION_MARKER="# mascarade-pg-backup-retention"

EXISTING="$(crontab -l 2>/dev/null | grep -v "$BACKUP_MARKER" | grep -v "$RETENTION_MARKER" || true)"

{
  printf "%s\n" "$EXISTING"
  echo "$BACKUP_CRON cd $REPO_DIR && $REPO_DIR/scripts/pg_backup.sh >/dev/null 2>&1 $BACKUP_MARKER"
  echo "$RETENTION_CRON cd $REPO_DIR && $REPO_DIR/scripts/pg_backup_retention.sh --days $RETENTION_DAYS >/dev/null 2>&1 $RETENTION_MARKER"
} | crontab -

echo "Backup automation installed in user crontab"
echo "  backup:    $BACKUP_CRON"
echo "  retention: $RETENTION_CRON (days=$RETENTION_DAYS)"
