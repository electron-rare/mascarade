---
applyTo: web/src/**/*.{ts,tsx}
description: "Use when editing the React bridge UI. Enforces routing, typed component, API-hook, and validation patterns without duplicating architecture docs."
---

# Web React Instructions

## Scope

Apply this file when modifying `web/src/**/*.{ts,tsx}`.
`web/` is a bridge sandbox; the main cockpit lives in the external `crazy_life` repository.


## Build & Test

```bash
cd web
npm run dev
npm run build
npm test -- --run
```

For API contract-sensitive changes, also validate API stack:

```bash
cd api
npm run build
npm test
```

## Required Patterns

- Keep strict typing in components, hooks, and API responses (no `any`).
- Reuse the existing API abstraction and hooks instead of ad hoc `fetch` in pages.
- Keep global state limited to auth/session; prefer local state for feature flows.
- Preserve route/layout patterns in `App.tsx` and current lazy-loading behavior.
- Preserve accessibility in touched views (labels, keyboard navigation, focus states).

## Frontend Boundary Rules

- Do not call `core/` directly from `web/`; calls must go through `api/`.
- Treat `web/` as a contract testbed for the cockpit. If a contract changes, reflect it in `crazy_life`.
- Avoid broad navigation/design rewrites in feature-local tasks.

## Key References (Link, Don’t Embed)

### Frontend implementation references
- [web/src/App.tsx](../../web/src/App.tsx)
- [web/src/api/client.ts](../../web/src/api/client.ts)
- [web/src/hooks/useApi.ts](../../web/src/hooks/useApi.ts)
- [web/src/hooks/useFetch.ts](../../web/src/hooks/useFetch.ts)
- [web/src/auth/AuthContext.tsx](../../web/src/auth/AuthContext.tsx)
- [web/src/components/ErrorBoundary.tsx](../../web/src/components/ErrorBoundary.tsx)
- [web/src/components/ui/Button.tsx](../../web/src/components/ui/Button.tsx)

### API contract references
- [api/src/index.ts](../../api/src/index.ts)
- [api/src/middleware/auth.ts](../../api/src/middleware/auth.ts)
- [api/src/middleware/error.ts](../../api/src/middleware/error.ts)
- [api/src/validation/schemas.ts](../../api/src/validation/schemas.ts)
- [api/src/routes/agents.ts](../../api/src/routes/agents.ts)
- [api/src/routes/health.test.ts](../../api/src/routes/health.test.ts)

### Documentation references
- [web/README.md](../../web/README.md)
- [docs/FRONTEND_SPEC.md](../../docs/FRONTEND_SPEC.md)
- [docs/API.md](../../docs/API.md)
- [.github/copilot-instructions.md](../copilot-instructions.md)

## Common Pitfalls

- Drift between `web/` and `crazy_life` after API changes.
- Bypassing shared API hooks and duplicating error handling.
- Breaking middleware expectations by assuming direct auth behavior in frontend.
- Shipping unvalidated frontend changes without `npm run build` and tests.