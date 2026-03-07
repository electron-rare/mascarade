#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERBOSE=0
ASSUME_YES=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: install_kicad_plugins.sh <command> [options]

Commands:
  list                                  Show available plugin bundles
  plugin-dir [--kicad-version VER]      Print the default KiCad plugin directory
  install <name|all> [options]          Install one or more plugin bundles
  help                                  Show this help

Bundles:
  fabrication-toolkit                   JLC/Fabrication Toolkit plugin
  kic-ai                                KIC-AI Assistant plugin
  all                                   Install all known bundles

Install options:
  --plugin-dir DIR                      Override target KiCad plugins directory
  --kicad-version VER                   KiCad version for the default plugin dir (default: 9.0)
  --yes                                 Overwrite existing bundle directories without prompting
  --dry-run                             Print actions without writing files
  -v, --verbose                         Print debug details
  -h, --help                            Show command help

Environment:
  KICAD_PLUGIN_DIR                      Same as --plugin-dir
  KICAD_VERSION                         Same as --kicad-version
EOF
}

log() {
  printf '[kicad-install] %s\n' "$*"
}

debug() {
  if [ "$VERBOSE" -eq 1 ]; then
    printf '[kicad-install][dbg] %s\n' "$*" >&2
  fi
}

die() {
  printf '[kicad-install][err] %s\n' "$*" >&2
  exit 1
}

default_plugin_dir() {
  local version="${1:-9.0}"
  case "$(uname -s)" in
    Linux)
      printf '%s/.config/kicad/%s/scripting/plugins\n' "$HOME" "$version"
      ;;
    Darwin)
      printf '%s/Library/Application Support/kicad/%s/scripting/plugins\n' "$HOME" "$version"
      ;;
    *)
      printf '%s/.config/kicad/%s/scripting/plugins\n' "$HOME" "$version"
      ;;
  esac
}

bundle_source_dir() {
  case "$1" in
    fabrication-toolkit)
      printf '%s/finetune/kicad_fabrication_toolkit\n' "$ROOT_DIR"
      ;;
    kic-ai)
      printf '%s/finetune/kicad_kic_ai\n' "$ROOT_DIR"
      ;;
    *)
      return 1
      ;;
  esac
}

bundle_target_name() {
  case "$1" in
    fabrication-toolkit)
      printf 'fabrication-toolkit\n'
      ;;
    kic-ai)
      printf 'com.jochem.kic-ai-assistant\n'
      ;;
    *)
      return 1
      ;;
  esac
}

bundle_entries() {
  case "$1" in
    fabrication-toolkit)
      printf '%s\n' metadata.json plugins resources assets LICENSE README.md
      ;;
    kic-ai)
      printf '%s\n' metadata.json plugins LICENSE README.md
      ;;
    *)
      return 1
      ;;
  esac
}

confirm_overwrite() {
  local target="$1"
  if [ ! -e "$target" ]; then
    return 0
  fi

  if [ "$ASSUME_YES" -eq 1 ]; then
    return 0
  fi

  if [ ! -t 0 ]; then
    die "Target exists: $target. Re-run with --yes to overwrite in non-interactive mode."
  fi

  printf 'Overwrite existing plugin at %s? [y/N] ' "$target" >&2
  local answer=""
  read -r answer
  case "$answer" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      die "Aborted by user."
      ;;
  esac
}

install_bundle() {
  local bundle="$1"
  local plugin_dir="$2"
  local source_dir target_name target_dir tmp_dir

  source_dir="$(bundle_source_dir "$bundle")" || die "Unknown bundle: $bundle"
  target_name="$(bundle_target_name "$bundle")" || die "Unknown bundle: $bundle"
  target_dir="${plugin_dir%/}/$target_name"

  [ -d "$source_dir" ] || die "Missing source directory: $source_dir"
  confirm_overwrite "$target_dir"

  log "Installing $bundle -> $target_dir"
  if [ "$DRY_RUN" -eq 1 ]; then
    while IFS= read -r entry; do
      debug "would copy $source_dir/$entry"
    done < <(bundle_entries "$bundle")
    return 0
  fi

  mkdir -p "$plugin_dir"
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN
  mkdir -p "$tmp_dir/$target_name"

  while IFS= read -r entry; do
    [ -e "$source_dir/$entry" ] || die "Missing bundle entry: $source_dir/$entry"
    debug "copy $source_dir/$entry -> $tmp_dir/$target_name/"
    cp -a "$source_dir/$entry" "$tmp_dir/$target_name/"
  done < <(bundle_entries "$bundle")

  rm -rf "$target_dir"
  mv "$tmp_dir/$target_name" "$target_dir"
  rm -rf "$tmp_dir"
  trap - RETURN
}

list_cmd() {
  cat <<'EOF'
fabrication-toolkit
kic-ai
EOF
}

plugin_dir_cmd() {
  local kicad_version="${KICAD_VERSION:-9.0}"

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --kicad-version)
        [ "$#" -ge 2 ] || die "--kicad-version requires a value"
        kicad_version="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option for plugin-dir: $1"
        ;;
    esac
  done

  default_plugin_dir "$kicad_version"
}

install_cmd() {
  [ "$#" -ge 1 ] || die "install requires a bundle name"

  local bundle="$1"
  shift
  local kicad_version="${KICAD_VERSION:-9.0}"
  local plugin_dir="${KICAD_PLUGIN_DIR:-}"

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --plugin-dir)
        [ "$#" -ge 2 ] || die "--plugin-dir requires a value"
        plugin_dir="$2"
        shift 2
        ;;
      --kicad-version)
        [ "$#" -ge 2 ] || die "--kicad-version requires a value"
        kicad_version="$2"
        shift 2
        ;;
      --yes)
        ASSUME_YES=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
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
        die "Unknown install option: $1"
        ;;
    esac
  done

  if [ -z "$plugin_dir" ]; then
    plugin_dir="$(default_plugin_dir "$kicad_version")"
  fi

  case "$bundle" in
    fabrication-toolkit|kic-ai)
      install_bundle "$bundle" "$plugin_dir"
      ;;
    all)
      install_bundle fabrication-toolkit "$plugin_dir"
      install_bundle kic-ai "$plugin_dir"
      ;;
    *)
      die "Unknown bundle: $bundle"
      ;;
  esac
}

main() {
  local cmd="${1:-help}"
  if [ "$#" -gt 0 ]; then
    shift
  fi

  case "$cmd" in
    list)
      list_cmd "$@"
      ;;
    plugin-dir)
      plugin_dir_cmd "$@"
      ;;
    install)
      install_cmd "$@"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      die "Unknown command: $cmd"
      ;;
  esac
}

main "$@"
