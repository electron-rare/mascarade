---
applyTo: "e2e/tests/**/*.spec.ts,e2e/mock-api/**/*.mjs,web/e2e/**/*.ts"
description: "Use when writing or reviewing Playwright E2E tests and mock API behavior."
---

# E2E Playwright Instructions

## Scope

Use this file for end-to-end tests in `e2e/` and Playwright tests in `web/e2e/`.

## Test Design

- Keep tests deterministic and isolated.
- Prefer explicit endpoint assertions over broad snapshot-like checks.
- Group by domain: `api/`, `web/`, `external/`.
- Use clear French test descriptions when matching existing files.

## Mock API Rules

- For API E2E tests, prefer routes in `e2e/mock-api/server.mjs`.
- Add minimal mock routes only for the tested behavior.
- Keep auth behavior aligned with fail-closed semantics:
  - no token -> 503 or 401 depending on gateway behavior under test
  - invalid token -> 401
  - valid token -> success path
- Avoid embedding secrets or real credentials in mock fixtures.

## Execution Rules

- From monorepo root, use config-aware command:

```bash
npm exec --prefix e2e playwright -- test --config e2e/playwright.config.ts <spec-or-folder> --project api
```

- From `e2e/`, use standard command:

```bash
npx playwright test <spec-or-folder> --project=api
```

- For web UI flows:

```bash
npm exec --prefix e2e playwright -- test --config e2e/playwright.config.ts tests/web --project web
```

## Validation Strategy

- After touching one spec: run that spec only.
- After touching shared mock routes: run all `tests/api/**/*.spec.ts`.
- For cross-cutting changes (config/mock/auth): run API + web projects.

## Pitfalls

- If `Project(s) "api" not found`, ensure command runs with `--config e2e/playwright.config.ts`.
- If no tests found, check relative path resolution from current working directory.
- Keep `webServer` startup expectations in sync with `playwright.config.ts`.