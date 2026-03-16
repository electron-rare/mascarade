#!/usr/bin/env bash
# scripts/backup.sh - Automated backup for critical Mascarade data
# Backs up: PostgreSQL DB, agent state, vector stores, fine-tune checkpoints

set -euo pipefail

# ── Configuration ──
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DRY_RUN="${DRY_RUN:-false}"

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

# Critical Docker volumes to backup
VOLUMES=(
    "postgres-data"              # PostgreSQL database (n8n, dify, langfuse)
    "core-data"                  # Core application data
    "qdrant-data"                # Vector store for agent memory (Mem0)
    "agent-factory-cockpit-data" # Agent factory state
    "neo4j-data"                 # Graph database (Graphiti)
    "ollama-data"                # Fine-tune models/checkpoints
    "redis-data"                 # Session/cache data
)

# Optional volumes (backed up if they exist)
OPTIONAL_VOLUMES=(
    "n8n-data"                   # N8N workflows
    "clickhouse-data"            # Analytics data (Langfuse)
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Helper functions ──
log() {
    echo -e "${BLUE}[backup]${NC} $*"
}

success() {
    echo -e "${GREEN}[backup]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[backup]${NC} $*" >&2
}

error() {
    echo -e "${RED}[backup]${NC} $*" >&2
}

die() {
    error "$*"
    exit 1
}

# ── Preflight checks ──
preflight_check() {
    log "Running preflight checks..."

    # Check if Docker is running (skip in dry-run mode)
    if ! docker info >/dev/null 2>&1; then
        if [[ "$DRY_RUN" == "false" ]]; then
            die "Docker is not running. Please start Docker and try again."
        else
            warn "Docker is not running (continuing in dry-run mode)"
        fi
    fi

    # Check if docker-compose is available
    if ! command -v docker >/dev/null 2>&1; then
        if [[ "$DRY_RUN" == "false" ]]; then
            die "docker command not found. Please install Docker."
        else
            warn "docker command not found (continuing in dry-run mode)"
        fi
    fi

    # Create backup directory
    if [[ "$DRY_RUN" == "false" ]]; then
        mkdir -p "$BACKUP_DIR"
        log "Backup directory: $BACKUP_DIR"
    else
        log "[DRY RUN] Would create backup directory: $BACKUP_DIR"
    fi

    success "Preflight checks passed"
}

# ── Backup PostgreSQL database ──
backup_postgres() {
    log "Backing up PostgreSQL database..."

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        warn "PostgreSQL container ($POSTGRES_CONTAINER) is not running, skipping database backup"
        return 0
    fi

    local dump_file="$BACKUP_DIR/postgres_dump.sql.gz"

    if [[ "$DRY_RUN" == "false" ]]; then
        # Use pg_dumpall to backup all databases including roles and permissions
        if docker exec "$POSTGRES_CONTAINER" pg_dumpall -U "$POSTGRES_USER" | gzip > "$dump_file"; then
            local size=$(du -h "$dump_file" | cut -f1)
            success "PostgreSQL backup complete: $dump_file ($size)"
        else
            error "PostgreSQL backup failed"
            return 1
        fi
    else
        log "[DRY RUN] Would backup PostgreSQL to: $dump_file"
    fi
}

# ── Backup Docker volume ──
backup_volume() {
    local volume_name="$1"
    local is_optional="${2:-false}"

    # Check if volume exists (skip check in dry-run mode)
    if [[ "$DRY_RUN" == "false" ]]; then
        if ! docker volume inspect "$volume_name" >/dev/null 2>&1; then
            if [[ "$is_optional" == "true" ]]; then
                log "Optional volume '$volume_name' does not exist, skipping"
                return 0
            else
                error "Critical volume '$volume_name' does not exist"
                return 1
            fi
        fi
    fi

    log "Backing up volume: $volume_name..."

    local archive_file="$BACKUP_DIR/${volume_name}.tar.gz"

    if [[ "$DRY_RUN" == "false" ]]; then
        # Use a temporary container to tar the volume contents
        if docker run --rm \
            -v "$volume_name:/data:ro" \
            -v "$BACKUP_DIR:/backup" \
            alpine:latest \
            tar czf "/backup/${volume_name}.tar.gz" -C /data . 2>/dev/null; then

            local size=$(du -h "$archive_file" | cut -f1)
            success "Volume backup complete: $volume_name ($size)"
        else
            error "Volume backup failed: $volume_name"
            return 1
        fi
    else
        log "[DRY RUN] Would backup volume '$volume_name' to: $archive_file"
    fi
}

# ── Backup fine-tune checkpoints (local files) ──
backup_finetune_checkpoints() {
    log "Backing up fine-tune checkpoints..."

    local finetune_dir="$ROOT_DIR/finetune"
    local checkpoints_patterns=(
        "checkpoints"
        "outputs"
        "models"
        "*.ckpt"
        "*.safetensors"
        "*.bin"
        "adapter_*.json"
    )

    # Find checkpoint files
    local found_files=()
    for pattern in "${checkpoints_patterns[@]}"; do
        while IFS= read -r -d '' file; do
            found_files+=("$file")
        done < <(find "$finetune_dir" -type f -name "$pattern" -print0 2>/dev/null || true)
    done

    if [[ ${#found_files[@]} -eq 0 ]]; then
        log "No fine-tune checkpoints found, skipping"
        return 0
    fi

    local archive_file="$BACKUP_DIR/finetune_checkpoints.tar.gz"

    if [[ "$DRY_RUN" == "false" ]]; then
        if tar czf "$archive_file" -C "$finetune_dir" . 2>/dev/null; then
            local size=$(du -h "$archive_file" | cut -f1)
            success "Fine-tune checkpoints backup complete ($size)"
        else
            warn "Fine-tune checkpoints backup had errors (may be incomplete)"
        fi
    else
        log "[DRY RUN] Would backup ${#found_files[@]} checkpoint files to: $archive_file"
    fi
}

# ── Generate backup manifest ──
generate_manifest() {
    log "Generating backup manifest..."

    local manifest_file="$BACKUP_DIR/manifest.json"

    if [[ "$DRY_RUN" == "false" ]]; then
        cat > "$manifest_file" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "hostname": "$(hostname)",
  "backup_dir": "$BACKUP_DIR",
  "mascarade_version": "$(cat "$ROOT_DIR/CHANGELOG.md" 2>/dev/null | grep -m1 "^## " | cut -d' ' -f2 || echo 'unknown')",
  "files": [
$(find "$BACKUP_DIR" -type f ! -name "manifest.json" -exec basename {} \; | sed 's/^/    "/' | sed 's/$/"/' | paste -sd, -)
  ]
}
EOF
        success "Manifest generated: $manifest_file"
    else
        log "[DRY RUN] Would generate manifest at: $manifest_file"
    fi
}

# ── Cleanup old backups ──
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."

    if [[ "$DRY_RUN" == "false" ]]; then
        # Find and delete backups older than retention period
        local deleted=0
        while IFS= read -r -d '' backup_path; do
            log "Deleting old backup: $(basename "$backup_path")"
            rm -rf "$backup_path"
            ((deleted++))
        done < <(find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" -mtime +"$RETENTION_DAYS" -print0 2>/dev/null || true)

        if [[ $deleted -gt 0 ]]; then
            success "Deleted $deleted old backup(s)"
        else
            log "No old backups to delete"
        fi
    else
        local count=$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" -mtime +"$RETENTION_DAYS" 2>/dev/null | wc -l | tr -d ' ')
        log "[DRY RUN] Would delete $count old backup(s)"
    fi
}

# ── Verify backup integrity ──
verify_backup() {
    log "Verifying backup integrity..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Skipping verification"
        return 0
    fi

    local errors=0

    # Check that manifest exists
    if [[ ! -f "$BACKUP_DIR/manifest.json" ]]; then
        error "Manifest file missing"
        ((errors++))
    fi

    # Check that PostgreSQL dump exists (if container was running)
    if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        if [[ ! -f "$BACKUP_DIR/postgres_dump.sql.gz" ]]; then
            error "PostgreSQL dump missing"
            ((errors++))
        fi
    fi

    # Verify archive integrity
    for archive in "$BACKUP_DIR"/*.tar.gz; do
        if [[ -f "$archive" ]]; then
            if ! gzip -t "$archive" 2>/dev/null; then
                error "Archive corrupted: $(basename "$archive")"
                ((errors++))
            fi
        fi
    done

    if [[ $errors -eq 0 ]]; then
        success "Backup verification passed"
        return 0
    else
        error "Backup verification failed with $errors error(s)"
        return 1
    fi
}

# ── Main backup routine ──
main() {
    log "Starting Mascarade backup (timestamp: $TIMESTAMP)"

    if [[ "$DRY_RUN" == "true" ]]; then
        warn "Running in DRY RUN mode - no changes will be made"
    fi

    # Run preflight checks
    preflight_check

    # Backup PostgreSQL database
    backup_postgres || die "PostgreSQL backup failed"

    # Backup critical volumes
    for volume in "${VOLUMES[@]}"; do
        backup_volume "$volume" false || die "Critical volume backup failed: $volume"
    done

    # Backup optional volumes
    for volume in "${OPTIONAL_VOLUMES[@]}"; do
        backup_volume "$volume" true || warn "Optional volume backup failed: $volume"
    done

    # Backup fine-tune checkpoints
    backup_finetune_checkpoints

    # Generate manifest
    generate_manifest

    # Verify backup
    verify_backup || die "Backup verification failed"

    # Cleanup old backups
    cleanup_old_backups

    if [[ "$DRY_RUN" == "false" ]]; then
        local total_size=$(du -sh "$BACKUP_DIR" | cut -f1)
        success "Backup complete! Total size: $total_size"
        success "Backup location: $BACKUP_DIR"
    else
        success "[DRY RUN] Backup simulation complete"
    fi
}

# ── Usage information ──
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Automated backup script for critical Mascarade data.

OPTIONS:
    --dry-run           Simulate backup without making changes
    --retention DAYS    Set retention period (default: 30 days)
    --help              Show this help message

ENVIRONMENT VARIABLES:
    BACKUP_ROOT                 Root directory for backups (default: ./backups)
    BACKUP_RETENTION_DAYS       Days to retain backups (default: 30)
    DRY_RUN                     Set to 'true' for dry run mode

EXAMPLES:
    # Normal backup
    bash scripts/backup.sh

    # Dry run to see what would be backed up
    bash scripts/backup.sh --dry-run

    # Custom retention period
    bash scripts/backup.sh --retention 60

    # Custom backup location
    BACKUP_ROOT=/mnt/backups bash scripts/backup.sh

EOF
}

# ── Parse command line arguments ──
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run main backup
main
