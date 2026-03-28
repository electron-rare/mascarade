# Mascarade Workspace Instructions

## Scope

This repository is a monorepo with three stacks:
- core/: Python FastAPI runtime
- api/: TypeScript Hono API
- web/: React Vite cockpit

## Commands

Core:
- cd core && python -m pytest
- cd core && ruff check mascarade/ tests/
- cd core && black mascarade/ tests/
- cd core && mypy mascarade/

API:
- cd api && npm run build
- cd api && npm test

Web:
- cd web && npm run build
- cd web && npm test -- --run

## Conventions

- Keep changes scoped to touched stack.
- Preserve public behavior unless change is explicit.
- Keep strict typing and existing validation patterns.
- Prefer minimal patches and run relevant checks after edits.

## References

- CLAUDE.md
- docs/ARCHITECTURE.md
- docs/api/README.md
- INTEGRATION_TESTING.md
- E2E_VERIFICATION.md