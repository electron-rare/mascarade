# Bash CLI/TUI Checklist

## Interface

- `--help` works and exits `0`
- invalid flag exits `2`
- `--verbose` enables debug logs
- `--yes` disables interactive confirmation

## Runtime

- script runs with `set -euo pipefail`
- temp files are removed on exit/signal
- no unquoted variable expansions in command args
- external command failures are handled or surfaced clearly

## TUI

- interactive prompts only when TTY is present
- fallback prompt works without `gum`
- CI/non-interactive mode does not hang

## Regression

- help output includes all primary options
- core command path tested with and without `--yes`
- failure path returns non-zero and readable error
