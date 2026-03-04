---
name: bash-cli-tui
description: Build, refactor, and debug Bash command-line and terminal UI scripts with safe argument parsing, non-interactive fallback, and robust error handling. Use when tasks involve shell tools with flags/subcommands, interactive prompts/menus (gum/dialog/select), colored output/logging, or portable scripting on Linux/macOS.
---

# Bash CLI TUI

## Overview

Implement reliable Bash CLIs and TUIs that work both interactively and in automation (`--yes`, CI, cron, SSH).

## Workflow

1. Inspect current script entrypoints, flags, and side effects.
2. Normalize CLI contract: `--help`, `--verbose`, `--yes`, clear exit codes.
3. Implement safe execution model: strict mode, quoting, cleanup traps, non-destructive defaults.
4. Add TUI layer with graceful fallback to plain prompts when no TTY/tooling.
5. Validate with a smoke matrix before merge.

## CLI Contract

- Use `set -euo pipefail` by default.
- Parse args with `case` loop, not positional guessing.
- Keep subcommands explicit (`cmd <subcommand> [options]`).
- Return stable codes:
  - `0` success
  - `2` usage/invalid args
  - `>=1` runtime errors
- Provide deterministic non-interactive mode (`--yes` / env flag).

## TUI Rules

- Prefer `gum` if available.
- Fallback to POSIX prompt when `gum` missing or non-TTY.
- Never block automation: if non-interactive and no explicit consent flag, fail fast with actionable message.
- Keep colors optional; respect `NO_COLOR`.

## Safety Rules

- Quote every variable expansion unless intentional word splitting.
- Use arrays for argument forwarding.
- Avoid destructive actions unless explicitly requested.
- Use `mktemp` for transient files and clean up with `trap`.
- Log commands before running them in verbose mode.

## Reusable Resources

- Read [references/checklist.md](references/checklist.md) for implementation/review checklist.
- Use [scripts/smoke_cli.sh](scripts/smoke_cli.sh) to validate basic CLI behavior.
