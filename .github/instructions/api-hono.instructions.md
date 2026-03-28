---
applyTo: api/src/**/*.ts
description: "Use when editing the Hono API layer. Enforces strict TypeScript and route validation patterns."
---

# API Hono Instructions

- Keep strict TypeScript typing.
- Reuse existing Zod validation patterns for payloads.
- Keep middleware behavior stable (auth/security/rate-limit/CORS order).
- Avoid unrelated refactors in endpoint-focused tasks.

Validation commands:
- cd api && npm run build
- cd api && npm test