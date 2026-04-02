# Repository Guidelines

## Current Focus
This repo is currently centered on three active areas:

- `api/src/routes/openburo*.ts` and `api/src/index.ts` for Open Buro app registry, events, search, connectors, and workspaces.
- `core/mascarade/integrations/nextcloud.py` for Nextcloud WebDAV sync used by datasets, model artifacts, and Argilla import flows.
- Tower-hosted services on `clems@192.168.0.120`, especially Drive (`:8086`, frontend gestionnaire), Nextcloud (`:8088`, backend stockage/WebDAV), and Open Buro health targets.
- Shared SSO callback on `https://auth.saillant.cc/_oauth` for forward-auth protected apps such as Dolibarr.

Keep contributor work aligned with these priorities before expanding into unrelated modules.

## Target Architecture
- Dolibarr: referentiel metier ERP/CRM
- Mascarade / Open Buro: orchestration and resolution layer
- Drive: frontend gestionnaire de fichiers
- Nextcloud: backend stockage / WebDAV
- Suite Numerique: edition via Docs / Impress / Spreadsheet

Do not turn Dolibarr into the primary document frontend. Dolibarr owns business entities, statuses, and document references; Drive + Nextcloud own storage, navigation, editing, sharing, and versioning.

## Project Structure & Ownership
`core/` is the Python 3.11 FastAPI engine; place domain logic, integrations, and tests there. `api/` is the TypeScript Hono gateway; Open Buro routes live in `api/src/routes/`. `web/` is the React cockpit. `e2e/` holds Playwright flows. Infra and deployment files live in `deploy/` and root `docker-compose*.yml`.

For current work, prefer these boundaries:

- Nextcloud sync and file semantics: `core/mascarade/integrations/nextcloud.py`
- Open Buro HTTP contracts and event bus: `api/src/routes/openburo-*.ts`
- Tower deployment assumptions: `deploy/`, `README.md`, and route health URLs

## Build, Test, and Development Commands
- `cd core && python -m pytest`: run Python tests.
- `cd core && python -m ruff check . && python -m black --check .`: lint and format-check Python.
- `cd api && npm run dev`: run the Open Buro gateway locally.
- `cd api && npm run build && npm test`: compile and run Vitest.
- `cd e2e && npm test`: run Playwright end-to-end checks.
- `docker compose -f docker-compose.yml -f docker-compose.test.yml up --build`: start the integrated stack.

## Coding Style & Naming Conventions
Python uses 4-space indentation, `snake_case`, and small integration helpers. TypeScript uses `camelCase` for functions and `PascalCase` for types and components. Match existing route naming: `openburo-events`, `openburo-search`, `openburo-workspaces`. Do not hardcode tokens, passwords, or host-specific secrets; use env vars instead.

## Open Buro & Nextcloud Rules
Open Buro changes must keep ports, internal callbacks, and health checks consistent with the API runtime on `:3100`. Current in-flight work already moves internal callbacks from `localhost:3000` to `localhost:3100` and removes hardcoded auth from notifications.
Forward-auth references should use the current shared callback host `auth.saillant.cc/_oauth`; do not introduce a second callback domain without updating both proxy layers and Keycloak client redirects.

Treat Drive and Nextcloud as linked but distinct surfaces: Drive is the file-manager frontend, while Nextcloud provides backend storage and WebDAV access. Product rule: when a file can be edited in the Suite Numerique, prefer opening it in the relevant editor instead of forcing a download. Nextcloud changes must stay in the WebDAV client, preserve remote path structure, and avoid embedding Tower credentials. If you change sync behavior, verify upload, download, directory listing, and Argilla import assumptions.
Use the Open Buro file-opening resolver for this behavior instead of hardcoding raw file URLs in the UI. The resolver should return an editor target first, Drive second, and direct download only as an explicit fallback.

For Dolibarr integration, model references explicitly: `entity_type`, `entity_id`, `nextcloud_path`, `drive_url`, `editor_url`, and sync metadata. Prefer standard trees such as `/clients/{client_ref}/devis/`, `/factures/`, `/commandes/`, `/contrats/`, and `/projets/{project_ref}/`.

## Testing & PR Expectations
Add or update tests for every Open Buro route or Nextcloud behavior you touch. Cover event publication, search fallback, workspace creation, and WebDAV edge cases where relevant. Include health checks compatible with Tower-style deployments where `status.php` may fail but authenticated WebDAV succeeds. Follow Conventional Commits such as `feat(openburo): ...`, `fix(nextcloud): ...`, or `ops(tower): ...`.

PRs should state:

- what changed on Open Buro or Nextcloud
- whether Tower assumptions changed
- which commands were run
- whether manual verification on `clems@192.168.0.120` is still required
