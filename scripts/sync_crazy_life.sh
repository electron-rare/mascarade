#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${CRAZY_LIFE_PREFIX:-web}"
REMOTE_NAME="${CRAZY_LIFE_REMOTE:-crazy_life}"
REMOTE_URL="${CRAZY_LIFE_REMOTE_URL:-https://github.com/electron-rare/crazy_life.git}"
TARGET_BRANCH="${CRAZY_LIFE_BRANCH:-main}"
ALLOW_DIRTY=0
FORCE_PUSH=0
VERBOSE=0

usage() {
  cat <<'EOF'
Usage: scripts/sync_crazy_life.sh <command> [options]

Commands:
  help            Show this help
  status          Show remote configuration and current subtree split SHA
  init-remote     Create/update the local git remote for crazy_life
  split           Print the current subtree split SHA for web/
  pull            Pull crazy_life back into web/ with git subtree
  sync-back       Alias for pull
  push            Push the web/ subtree to the crazy_life repository

Options:
  --remote <name>     Remote name to use (default: crazy_life)
  --remote-url <url>  Remote URL to use/create
  --branch <name>     Target branch on the frontend repo (default: main)
  --prefix <path>     Subtree path to split (default: web)
  --allow-dirty       Allow running with a dirty worktree (HEAD only is pushed)
  --force             Force-push the split branch
  -v, --verbose       Show debug output
  -h, --help          Show this help

Examples:
  scripts/sync_crazy_life.sh init-remote
  scripts/sync_crazy_life.sh status
  scripts/sync_crazy_life.sh pull
  scripts/sync_crazy_life.sh push --allow-dirty --force
EOF
}

log() {
  printf '[crazy-life] %s\n' "$*" >&2
}

debug() {
  if [[ "$VERBOSE" -eq 1 ]]; then
    printf '[crazy-life][dbg] %s\n' "$*" >&2
  fi
}

die() {
  printf '[crazy-life][err] %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

ensure_repo() {
  [[ -d "$ROOT_DIR/.git" ]] || die "Not a git repository: $ROOT_DIR"
  [[ -d "$ROOT_DIR/$PREFIX" ]] || die "Missing subtree path: $ROOT_DIR/$PREFIX"
}

worktree_dirty() {
  [[ -n "$(git -C "$ROOT_DIR" status --short)" ]]
}

ensure_clean_or_warn() {
  if worktree_dirty; then
    if [[ "$ALLOW_DIRTY" -eq 1 ]]; then
      log "Dirty worktree detected; only committed HEAD content from $PREFIX will be synced."
      return
    fi
    die "Dirty worktree detected. Commit/stash changes first or rerun with --allow-dirty."
  fi
}

ensure_remote() {
  local current_url=""
  if git -C "$ROOT_DIR" remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
    current_url="$(git -C "$ROOT_DIR" remote get-url "$REMOTE_NAME")"
    if [[ "$current_url" != "$REMOTE_URL" ]]; then
      log "Updating remote $REMOTE_NAME -> $REMOTE_URL"
      git -C "$ROOT_DIR" remote set-url "$REMOTE_NAME" "$REMOTE_URL"
    else
      debug "Remote $REMOTE_NAME already points to $REMOTE_URL"
    fi
    return
  fi

  log "Adding remote $REMOTE_NAME -> $REMOTE_URL"
  git -C "$ROOT_DIR" remote add "$REMOTE_NAME" "$REMOTE_URL"
}

compute_split_sha() {
  ensure_clean_or_warn
  debug "Computing subtree split for $PREFIX"
  git -C "$ROOT_DIR" subtree split --prefix="$PREFIX" HEAD
}

status_cmd() {
  local split_sha
  split_sha="$(compute_split_sha)"
  if git -C "$ROOT_DIR" remote get-url "$REMOTE_NAME" >/dev/null 2>&1; then
    log "remote: $REMOTE_NAME -> $(git -C "$ROOT_DIR" remote get-url "$REMOTE_NAME")"
  else
    log "remote: $REMOTE_NAME (not configured)"
  fi
  log "prefix: $PREFIX"
  log "target branch: $TARGET_BRANCH"
  log "split sha: $split_sha"
}

split_cmd() {
  compute_split_sha
}

push_cmd() {
  local split_sha
  require_cmd git
  ensure_remote
  split_sha="$(compute_split_sha)"

  log "Pushing $PREFIX subtree ($split_sha) to $REMOTE_NAME/$TARGET_BRANCH"
  if [[ "$FORCE_PUSH" -eq 1 ]]; then
    git -C "$ROOT_DIR" push --force "$REMOTE_NAME" "$split_sha:$TARGET_BRANCH"
  else
    git -C "$ROOT_DIR" push "$REMOTE_NAME" "$split_sha:$TARGET_BRANCH"
  fi
}

pull_cmd() {
  require_cmd git
  if worktree_dirty; then
    die "Dirty worktree detected. Commit/stash changes before pulling crazy_life back into $PREFIX."
  fi
  ensure_remote
  log "Fetching $REMOTE_NAME/$TARGET_BRANCH"
  git -C "$ROOT_DIR" fetch "$REMOTE_NAME" "$TARGET_BRANCH"
  log "Pulling $REMOTE_NAME/$TARGET_BRANCH into $PREFIX (squash)"
  git -C "$ROOT_DIR" subtree pull --prefix="$PREFIX" "$REMOTE_NAME" "$TARGET_BRANCH" --squash
}

COMMAND="help"

while [[ $# -gt 0 ]]; do
  case "$1" in
    help|status|init-remote|split|pull|sync-back|push)
      COMMAND="$1"
      shift
      ;;
    --remote)
      REMOTE_NAME="${2:-}"
      shift 2
      ;;
    --remote-url)
      REMOTE_URL="${2:-}"
      shift 2
      ;;
    --branch)
      TARGET_BRANCH="${2:-}"
      shift 2
      ;;
    --prefix)
      PREFIX="${2:-}"
      shift 2
      ;;
    --allow-dirty)
      ALLOW_DIRTY=1
      shift
      ;;
    --force)
      FORCE_PUSH=1
      shift
      ;;
    -v|--verbose)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

ensure_repo

case "$COMMAND" in
  help)
    usage
    ;;
  status)
    status_cmd
    ;;
  init-remote)
    ensure_remote
    ;;
  split)
    split_cmd
    ;;
  pull|sync-back)
    pull_cmd
    ;;
  push)
    push_cmd
    ;;
  *)
    die "Unknown command: $COMMAND"
    ;;
esac
