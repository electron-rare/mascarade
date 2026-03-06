#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_DIR/backups/postgres}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
DB_NAME="${POSTGRES_DB:-mascarade}"
DB_USER="${POSTGRES_USER:-mascarade}"
OUT_FILE="$BACKUP_DIR/${DB_NAME}_${TS}.dump"
TMP_FILE="$(mktemp "$BACKUP_DIR/${DB_NAME}_${TS}.tmp.XXXXXX")"

cleanup_tmp() {
  rm -f "$TMP_FILE"
}
trap cleanup_tmp EXIT

cd "$REPO_DIR"
docker compose --env-file "$ENV_FILE" -f "$REPO_DIR/docker-compose.yml" exec -T postgres \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$TMP_FILE"

mv "$TMP_FILE" "$OUT_FILE"
trap - EXIT

echo "Backup created: $OUT_FILE"
