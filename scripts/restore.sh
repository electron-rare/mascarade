#!/usr/bin/env bash
# scripts/restore.sh - Restore Mascarade data from backup
# Restores: PostgreSQL DB, agent state, vector stores, fine-tune checkpoints

set -euo pipefail

# ── Configuration ──
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
BACKUP_DIR=""
DRY_RUN="${DRY_RUN:-false}"
FORCE="${FORCE:-false}"

# Load environment variables if .env exists
# Use grep to filter out comments and malformed lines
if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$line" ]] && continue
        # Only export valid variable assignments (key=value format)
        if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*=.* ]]; then
            eval "export $line" 2>/dev/null || true
        fi
    done < "$ROOT_DIR/.env"
    set +a
fi

# PostgreSQL connection details from .env
POSTGRES_USER="${POSTGRES_USER:-mascarade}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
POSTGRES_DB="${POSTGRES_DB:-mascarade}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-mascarade-postgres}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Helper functions ──
log() {
    echo -e "${BLUE}[restore]${NC} $*"
}

success() {
    echo -e "${GREEN}[restore]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[restore]${NC} $*" >&2
}

error() {
    echo -e "${RED}[restore]${NC} $*" >&2
}

die() {
    error "$*"
    exit 1
}

confirm() {
    local prompt="$1"
    if [[ "$FORCE" == "true" ]]; then
        return 0
    fi

    echo -e -n "${YELLOW}[restore]${NC} $prompt (yes/no): " >&2
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# ── List available backups ──
list_backups() {
    log "Available backups in $BACKUP_ROOT:"
    echo ""

    if [[ ! -d "$BACKUP_ROOT" ]]; then
        warn "Backup directory does not exist: $BACKUP_ROOT"
        return 1
    fi

    local count=0
    while IFS= read -r -d '' backup_path; do
        local timestamp=$(basename "$backup_path")
        local size=$(du -sh "$backup_path" | cut -f1)
        local date=$(date -r "$backup_path" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$backup_path" 2>/dev/null || echo "unknown")

        # Check for manifest
        local has_manifest="✗"
        if [[ -f "$backup_path/manifest.json" ]]; then
            has_manifest="✓"
        fi

        echo "  [$count] $timestamp - $size - $date (manifest: $has_manifest)"
        ((count++))
    done < <(find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" -print0 2>/dev/null | sort -rz || true)

    if [[ $count -eq 0 ]]; then
        warn "No backups found"
        return 1
    fi

    echo ""
    return 0
}

# ── Select backup to restore ──
select_backup() {
    local backup_timestamp="$1"

    if [[ -z "$backup_timestamp" ]]; then
        # List backups and let user choose
        list_backups || die "No backups available"

        echo -n "Enter backup timestamp (e.g., 20260316_120000) or 'latest': "
        read -r backup_timestamp
    fi

    if [[ "$backup_timestamp" == "latest" ]]; then
        # Find most recent backup
        BACKUP_DIR=$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" 2>/dev/null | sort -r | head -n1)
        if [[ -z "$BACKUP_DIR" ]]; then
            die "No backups found"
        fi
        log "Selected latest backup: $(basename "$BACKUP_DIR")"
    else
        BACKUP_DIR="$BACKUP_ROOT/$backup_timestamp"
    fi

    if [[ ! -d "$BACKUP_DIR" ]]; then
        die "Backup not found: $BACKUP_DIR"
    fi

    # Display backup info
    if [[ -f "$BACKUP_DIR/manifest.json" ]]; then
        log "Backup manifest:"
        cat "$BACKUP_DIR/manifest.json" | grep -E "(timestamp|date|mascarade_version)" | sed 's/^/  /'
    else
        warn "No manifest found in backup (this may be an incomplete backup)"
    fi
}

# ── Preflight checks ──
preflight_check() {
    log "Running preflight checks..."

    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        die "Docker is not running. Please start Docker and try again."
    fi

    # Check if docker-compose is available
    if ! command -v docker >/dev/null 2>&1; then
        die "docker command not found. Please install Docker."
    fi

    # Verify backup directory exists
    if [[ ! -d "$BACKUP_DIR" ]]; then
        die "Backup directory does not exist: $BACKUP_DIR"
    fi

    # Warn about data loss
    warn "═══════════════════════════════════════════════════════════"
    warn "                    ⚠️  WARNING  ⚠️"
    warn "═══════════════════════════════════════════════════════════"
    warn "This operation will OVERWRITE existing data!"
    warn "All current data will be PERMANENTLY DELETED and replaced"
    warn "with data from the backup."
    warn ""
    warn "Backup source: $(basename "$BACKUP_DIR")"
    warn "═══════════════════════════════════════════════════════════"
    echo ""

    if ! confirm "Are you sure you want to continue?"; then
        die "Restore cancelled by user"
    fi

    # Recommend stopping services
    warn "It is strongly recommended to stop all services before restoring."
    if confirm "Stop all services now?"; then
        log "Stopping services..."
        if [[ "$DRY_RUN" == "false" ]]; then
            docker compose -f "$ROOT_DIR/docker-compose.yml" down || warn "Failed to stop services (they may not be running)"
        else
            log "[DRY RUN] Would stop services"
        fi
    else
        warn "Continuing with services potentially running - this may cause issues"
    fi

    success "Preflight checks complete"
}

# ── Restore PostgreSQL database ──
restore_postgres() {
    local dump_file="$BACKUP_DIR/postgres_dump.sql.gz"

    if [[ ! -f "$dump_file" ]]; then
        warn "PostgreSQL dump not found in backup, skipping"
        return 0
    fi

    log "Restoring PostgreSQL database..."

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        warn "PostgreSQL container is not running. Starting it..."
        if [[ "$DRY_RUN" == "false" ]]; then
            docker compose -f "$ROOT_DIR/docker-compose.yml" up -d postgres
            sleep 5  # Wait for PostgreSQL to be ready
        else
            log "[DRY RUN] Would start PostgreSQL container"
        fi
    fi

    if [[ "$DRY_RUN" == "false" ]]; then
        # Restore database
        if gunzip -c "$dump_file" | docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER"; then
            success "PostgreSQL restore complete"
        else
            error "PostgreSQL restore failed"
            return 1
        fi
    else
        log "[DRY RUN] Would restore PostgreSQL from: $dump_file"
    fi
}

# ── Restore Docker volume ──
restore_volume() {
    local volume_name="$1"
    local archive_file="$BACKUP_DIR/${volume_name}.tar.gz"

    if [[ ! -f "$archive_file" ]]; then
        warn "Archive not found for volume '$volume_name', skipping"
        return 0
    fi

    log "Restoring volume: $volume_name..."

    if [[ "$DRY_RUN" == "false" ]]; then
        # Remove existing volume if it exists
        if docker volume inspect "$volume_name" >/dev/null 2>&1; then
            log "Removing existing volume: $volume_name"
            docker volume rm "$volume_name" 2>/dev/null || warn "Could not remove volume (may be in use)"
        fi

        # Create new volume
        docker volume create "$volume_name" >/dev/null

        # Restore volume contents
        if docker run --rm \
            -v "$volume_name:/data" \
            -v "$BACKUP_DIR:/backup:ro" \
            alpine:latest \
            sh -c "cd /data && tar xzf /backup/${volume_name}.tar.gz" 2>/dev/null; then

            success "Volume restore complete: $volume_name"
        else
            error "Volume restore failed: $volume_name"
            return 1
        fi
    else
        log "[DRY RUN] Would restore volume '$volume_name' from: $archive_file"
    fi
}

# ── Restore fine-tune checkpoints ──
restore_finetune_checkpoints() {
    local archive_file="$BACKUP_DIR/finetune_checkpoints.tar.gz"

    if [[ ! -f "$archive_file" ]]; then
        log "No fine-tune checkpoints in backup, skipping"
        return 0
    fi

    log "Restoring fine-tune checkpoints..."

    local finetune_dir="$ROOT_DIR/finetune"

    if [[ "$DRY_RUN" == "false" ]]; then
        # Create finetune directory if it doesn't exist
        mkdir -p "$finetune_dir"

        # Extract checkpoints
        if tar xzf "$archive_file" -C "$finetune_dir"; then
            success "Fine-tune checkpoints restore complete"
        else
            error "Fine-tune checkpoints restore failed"
            return 1
        fi
    else
        log "[DRY RUN] Would restore fine-tune checkpoints to: $finetune_dir"
    fi
}

# ── Main restore routine ──
main() {
    log "Starting Mascarade restore"

    if [[ "$DRY_RUN" == "true" ]]; then
        warn "Running in DRY RUN mode - no changes will be made"
    fi

    # Run preflight checks
    preflight_check

    # Restore PostgreSQL database
    restore_postgres || die "PostgreSQL restore failed"

    # Restore all volumes found in backup
    for archive in "$BACKUP_DIR"/*.tar.gz; do
        if [[ -f "$archive" ]]; then
            local volume_name=$(basename "$archive" .tar.gz)
            # Skip checkpoint archive (handled separately)
            if [[ "$volume_name" != "finetune_checkpoints" ]]; then
                restore_volume "$volume_name" || warn "Failed to restore volume: $volume_name"
            fi
        fi
    done

    # Restore fine-tune checkpoints
    restore_finetune_checkpoints

    if [[ "$DRY_RUN" == "false" ]]; then
        success "Restore complete!"
        log ""
        log "Next steps:"
        log "  1. Start services: docker compose up -d"
        log "  2. Verify services are healthy: docker compose ps"
        log "  3. Check logs for any errors: docker compose logs -f"
    else
        success "[DRY RUN] Restore simulation complete"
    fi
}

# ── Usage information ──
usage() {
    cat <<EOF
Usage: $0 [OPTIONS] [BACKUP_TIMESTAMP]

Restore Mascarade data from a backup.

ARGUMENTS:
    BACKUP_TIMESTAMP    Timestamp of backup to restore (e.g., 20260316_120000)
                        Use 'latest' for most recent backup
                        Omit to select interactively

OPTIONS:
    --dry-run           Simulate restore without making changes
    --force             Skip confirmation prompts
    --list              List available backups and exit
    --help              Show this help message

ENVIRONMENT VARIABLES:
    BACKUP_ROOT         Root directory for backups (default: ./backups)
    DRY_RUN             Set to 'true' for dry run mode
    FORCE               Set to 'true' to skip confirmations

EXAMPLES:
    # List available backups
    bash scripts/restore.sh --list

    # Restore latest backup (interactive)
    bash scripts/restore.sh latest

    # Restore specific backup
    bash scripts/restore.sh 20260316_120000

    # Dry run to see what would be restored
    bash scripts/restore.sh --dry-run latest

    # Force restore without prompts
    bash scripts/restore.sh --force latest

    # Custom backup location
    BACKUP_ROOT=/mnt/backups bash scripts/restore.sh latest

⚠️  WARNING: This operation will OVERWRITE existing data!
    Make sure to backup current data before restoring.

EOF
}

# ── Parse command line arguments ──
BACKUP_TIMESTAMP=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --list)
            list_backups
            exit 0
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            BACKUP_TIMESTAMP="$1"
            shift
            ;;
    esac
done

# Select backup to restore
select_backup "$BACKUP_TIMESTAMP"

# Run main restore
main
