---
applyTo: "**/*"
description: "Use when setting up local dev environments, troubleshooting startup, or validating prerequisites."
---

# Dev Environment Instructions

## Scope

Use this guide for local setup and troubleshooting.
Do not duplicate stack-specific coding conventions already covered in dedicated instruction files.

## Setup Order

1. Confirm tool versions.
2. Install dependencies per stack.
3. Configure environment variables.
4. Run health checks.

## Toolchain Baseline

- Python: 3.11+
- Node.js: 20+
- npm: 10+
- Docker with Compose plugin

## Dependency Bootstrap

### Core

```bash
cd core
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### API

```bash
cd api
npm install
```

### Web

```bash
cd web
npm install
```

## Validation

### Core

```bash
cd core
python -m pytest -q
ruff check mascarade/ tests/
mypy mascarade/
```

### API

```bash
cd api
npm run build
npm test
```

### Web

```bash
cd web
npm run build
npm test -- --run
```

## Troubleshooting

- Python import errors: activate core virtual environment.
- Node build failures: reinstall dependencies with npm install.
- Docker conflicts: verify ports 8100, 3100, 5173 are free.

## References

- [CLAUDE.md](../../CLAUDE.md)
- [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)
- [docs/API.md](../../docs/API.md)