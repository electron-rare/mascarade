---
applyTo: api/src/**/*.ts
description: "Use when editing the Hono API layer. Enforces strict TypeScript and route validation patterns."
---

# API Hono Instructions

## Core Principles

- **Strict TypeScript**: `strict: true` in tsconfig.json; no `any` or implicit `unknown`.
- **Zod Validation**: All request payloads validated via Zod schemas; runtime safety at API boundaries.
- **Middleware Order (Immutable)**: `auth → rate-limit → CORS`. Never reorder.
- **RESTful Routes**: Use `/v1/*` prefix for versioning; `/openburo/*` for interoperability.
- **Async Handlers**: All async functions; use `await` for upstream core/ calls.
- **Error Handling**: Return appropriate HTTP codes (400 validation, 401 auth, 403 forbidden, 500 server).

## Middleware Invariants (CRITICAL)

```typescript
// Order in src/middleware/:
// 1. Authentication (verify JWT/session)
// 2. Rate Limiting (check quotas)
// 3. CORS (allow origins)
// ❌ NEVER reorder; security depends on auth before rate-limit
```

## Pattern Examples

### Zod Validation Schema
```typescript
import { z } from "zod";

const CoordinationRequestSchema = z.object({
  task: z.string().max(200),
  domain: z.string().optional(),
  mode: z.enum(["sequential", "parallel", "pipeline"]).optional(),
});

export type CoordinationRequest = z.infer<typeof CoordinationRequestSchema>;
```

### Hono Route Handler
```typescript
import { Hono } from "hono";
import { requireAuth } from "../middleware/auth";

const app = new Hono();

app.post("/v1/api/coordination/run", requireAuth, async (c) => {
  const body = await c.req.json();
  const parsed = CoordinationRequestSchema.safeParse(body);
  if (!parsed.success) return c.json({ error: "Invalid request" }, 422);
  
  return c.json(await coreProxy.post("/coordination", parsed.data), 200);
});
```

### Error Responses
```typescript
// Validation error (422)
return c.json({ error: "Invalid domain", details: ["domain must match pattern"] }, 422);

// Auth error (401)
return c.json({ error: "Unauthorized" }, 401);

// Upstream error (5xx)
return c.json({ error: "Core service failed" }, 503);
```

## Dependencies & Proxying to core/

- **No Python imports in api/**; call core/ via HTTP only.
- Use `httpx.AsyncClient` wrapper (created in api/src/lib/core-proxy.ts).
- Timeout: 30s for LLM calls; 5s for agent selection.

## Validation Commands

```bash
cd api
npm run build  # Compile TypeScript
npm test       # Run vitest suite (~458 tests)
```

## References

- [api/src/middleware/](../../api/src/middleware/) — Auth / Rate-Limit / CORS order
- [api/src/types/](../../api/src/types/) — Zod validation schemas
- [docs/API.md](../../docs/API.md) — API contract with core/