#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"
BACKUP_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-file)
      BACKUP_FILE="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$BACKUP_FILE" ]]; then
  echo "Usage: $0 --backup-file /path/to/backup.dump" >&2
  exit 2
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

cd "$REPO_DIR"
cat "$BACKUP_FILE" | docker compose --env-file "$ENV_FILE" -f "$REPO_DIR/docker-compose.yml" exec -T postgres sh -lc \
  'cat >/tmp/backup_verify.dump && pg_restore -l /tmp/backup_verify.dump >/dev/null && rm -f /tmp/backup_verify.dump'

echo "Backup verification passed: $BACKUP_FILE"
