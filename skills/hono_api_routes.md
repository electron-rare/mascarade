# Hono API Routes

## Overview
Mascarade's TypeScript API uses the Hono framework for lightweight, fast HTTP routing.

## Basic Route Structure

### File: `api/src/routes/agents.ts`
```typescript
import { Hono } from 'hono'
import { z } from 'zod'
import { zValidator } from '@hono/zod-validator'

const app = new Hono()

// Health check endpoint
app.get('/health', (c) => {
  return c.json({ status: 'ok', timestamp: Date.now() })
})

// Agent execution endpoint
const agentSchema = z.object({
  agent_id: z.string(),
  input: z.record(z.any()),
  strategy: z.enum(['best', 'cheapest', 'fastest', 'specific']).default('best')
})

app.post('/agents/execute', zValidator('json', agentSchema), async (c) => {
  const { agent_id, input, strategy } = c.req.valid('json')
  
  try {
    const result = await executeAgent(agent_id, input, strategy)
    return c.json({ success: true, result })
  } catch (error) {
    return c.json({ success: false, error: error.message }, 500)
  }
})

export default app
```

## Core API Patterns

### 1. Input Validation with Zod
```typescript
const createAgentSchema = z.object({
  name: z.string().min(3),
  description: z.string().optional(),
  config: z.record(z.any())
})

app.post('/agents', zValidator('json', createAgentSchema), async (c) => {
  const data = c.req.valid('json')
  // data is now type-safe
})
```

### 2. Error Handling Middleware
```typescript
app.onError((err, c) => {
  console.error(err)
  return c.json(
    { error: 'Internal Server Error' },
    500
  )
})
```

### 3. Async Route Handlers
```typescript
app.post('/agents/:id/execute', async (c) => {
  const agentId = c.req.param('id')
  const payload = await c.req.json()
  
  const result = await coreClient.execute(agentId, payload)
  return c.json(result)
})
```

### 4. Dependency Injection
```typescript
// Create app with dependencies
const app = new Hono<{ 
  Variables: { 
    coreClient: CoreClient 
    db: Database 
  } 
}>()

// Middleware to inject dependencies
app.use('*', async (c, next) => {
  c.set('coreClient', new CoreClient())
  c.set('db', new Database())
  await next()
})

// Usage in route
app.get('/agents', async (c) => {
  const db = c.get('db')
  const agents = await db.listAgents()
  return c.json(agents)
})
```

## Testing API Routes

```typescript
import { describe, it, expect } from 'vitest'
import { Hono } from 'hono'

const app = new Hono()
app.get('/test', (c) => c.json({ message: 'hello' }))

describe('API Routes', () => {
  it('should return hello message', async () => {
    const res = await app.request('/test')
    const body = await res.json()
    expect(body.message).toBe('hello')
  })
})
```

## Best Practices

1. **Type Safety**: Always use Zod for input validation
2. **Error Handling**: Consistent error responses (always JSON)
3. **Async/Await**: All route handlers should be async
4. **Dependency Injection**: Use Hono's context for shared services
5. **Modular Routes**: Split routes by domain (agents, health, etc.)
6. **Documentation**: Use OpenAPI/Swagger for API docs