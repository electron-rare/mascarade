#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$REPO_DIR/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      RETENTION_DAYS="${2:-14}"
      shift 2
      ;;
    --backup-dir)
      BACKUP_DIR="${2:-$BACKUP_DIR}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "Backup directory does not exist, nothing to purge: $BACKUP_DIR"
  exit 0
fi

DELETED=$(find "$BACKUP_DIR" -type f -name '*.dump' -mtime "+$RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')
echo "Deleted $DELETED backup file(s) older than $RETENTION_DAYS day(s) from $BACKUP_DIR"
