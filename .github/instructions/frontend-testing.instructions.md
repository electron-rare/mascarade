---
applyTo: web/src/**/*.{ts,tsx}
description: "Use when adding or reviewing frontend tests/checks for responsive behavior, accessibility, API error handling, and UI smoke paths."
---

# Frontend Testing Checklist

## Scope

Use this checklist for frontend PRs that touch `web/src/**/*.{ts,tsx}`.
Focus on stability checks; avoid redesign discussions here.

## 1) Responsive

- Verify key screens at `320px`, `768px`, and `>=1280px`.
- Ensure no horizontal overflow on primary pages.
- Confirm critical actions remain accessible without hover.
- Validate loading/error/empty states on small viewport.

## 2) Accessibility (a11y)

- Inputs have labels or accessible names.
- Buttons/interactive elements are keyboard reachable.
- Focus order is logical across form and modal flows.
- Error messages are visible and understandable.
- Avoid color-only status cues (include text/icon labels).

## 3) API Error Handling

- 401 path handled via existing auth/session behavior.
- 404/422/500 paths render user-friendly errors.
- Network timeout/abort does not leave infinite loader.
- Retry path available where workflow is recoverable.
- No raw backend stack traces exposed in UI.

## 4) UI Smoke Paths

Run smoke checks on high-value routes and flows:

- App shell loads without runtime error.
- Main navigation between core pages works.
- A primary CRUD or submission flow completes.
- ErrorBoundary fallback is reachable when forced.
- One API-backed page handles success + failure.

## 5) Required Validation Commands

```bash
cd web
npm run build
npm test -- --run
```

If API contract was touched:

```bash
cd api
npm run build
npm test
```

## 6) References

- [web/src/App.tsx](../../web/src/App.tsx)
- [web/src/hooks/useApi.ts](../../web/src/hooks/useApi.ts)
- [web/src/hooks/useFetch.ts](../../web/src/hooks/useFetch.ts)
- [web/src/components/ErrorBoundary.tsx](../../web/src/components/ErrorBoundary.tsx)
- [api/src/middleware/error.ts](../../api/src/middleware/error.ts)
- [docs/FRONTEND_SPEC.md](../../docs/FRONTEND_SPEC.md)