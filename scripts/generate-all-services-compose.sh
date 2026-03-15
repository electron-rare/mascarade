#!/usr/bin/env bash
# Temporary script to generate docker-compose.yml with ALL services for profile testing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source dependencies
source "$REPO_DIR/scripts/lib.sh"
source "$REPO_DIR/scripts/services.sh"
source "$REPO_DIR/scripts/compose.sh"

# Enable all services
for id in "${SVC_IDS[@]}"; do
    SVC_ON[$id]="1"
done

# Generate docker-compose.yml with all services
generate_compose "$REPO_DIR/docker-compose.yml"
echo "✓ Generated docker-compose.yml with all services"
