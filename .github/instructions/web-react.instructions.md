---
applyTo: web/src/**/*.{ts,tsx}
description: "Use when editing the React cockpit. Enforces existing routing/component patterns and focused validation."
---

# Web React Instructions

- Keep components typed and props-driven.
- Follow existing route and page patterns in web/src/.
- Avoid broad style/navigation rewrites in feature-local tasks.
- Preserve responsiveness and accessibility in touched views.

Validation commands:
- cd web && npm run build
- cd web && npm test -- --run