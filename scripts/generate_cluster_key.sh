#!/bin/bash
###############################################################################
# Generate secure P2P cluster shared key
#
# Usage:
#   bash scripts/generate_cluster_key.sh           # Generate and display
#   bash scripts/generate_cluster_key.sh >> .env   # Append to .env file
#   export $(bash scripts/generate_cluster_key.sh) # Export to environment
#
# This script generates a cryptographically secure 32-byte random key,
# hashes it with SHA256, and outputs the result as CLUSTER_SHARED_KEY=<value>
# suitable for use in .env files or direct environment variable export.
#
# The key is:
# - Randomly generated from /dev/urandom (256 bits of entropy)
# - Base64-encoded for portability
# - SHA256-hashed for additional cryptographic strength
# - Suitable for use in P2P mesh cluster authentication
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function: Print error message and exit
error_exit() {
    echo -e "${RED}ERROR: $1${NC}" >&2
    exit 1
}

# Function: Print success message
success_msg() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function: Print warning message
warning_msg() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check for required commands
check_commands() {
    for cmd in openssl base64 sha256sum; do
        if ! command -v "$cmd" &> /dev/null; then
            error_exit "Required command '$cmd' not found. Please install it."
        fi
    done
}

# Generate secure cluster key
generate_cluster_key() {
    # Generate 32 bytes (256 bits) of random data
    local random_bytes=$(openssl rand -base64 32)
    
    # SHA256 hash for additional security
    local cluster_key=$(echo -n "$random_bytes" | sha256sum | awk '{print $1}')
    
    echo "$cluster_key"
}

# Validate key format
validate_key() {
    local key="$1"
    
    # Should be exactly 64 hex characters (SHA256 output)
    if [[ ! $key =~ ^[a-f0-9]{64}$ ]]; then
        error_exit "Generated key has invalid format: $key"
    fi
}

# Main execution
main() {
    check_commands
    
    # Generate the key
    local cluster_key=$(generate_cluster_key)
    validate_key "$cluster_key"
    
    # Output in format suitable for .env or export
    echo "CLUSTER_SHARED_KEY=$cluster_key"
    
    # Log to stderr for visibility when piping
    echo -e "${GREEN}Generated secure cluster key (256-bit SHA256)${NC}" >&2
    echo -e "Key length: ${#cluster_key} characters (hex, 64 chars = 256 bits)" >&2
}

main "$@"
