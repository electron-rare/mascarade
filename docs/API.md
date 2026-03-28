# Mascarade API Reference

Complete endpoint reference for the Mascarade API Gateway (Hono, port 3100) and Core Engine (FastAPI, port 8100).

**Base URLs:**

- API Gateway: `https://mascarade.saillant.cc` (production) / `http://localhost:3100` (dev)
- Core Engine: `http://localhost:8100` (internal, not exposed publicly)

**Authentication:** Most public-facing endpoints require no auth. Routes under `/api/*` require a Bearer token unless `MASCARADE_ALLOW_PUBLIC_API=true` is set.

---

## Public Endpoints (no auth required)

### Health

#### `GET /health`

Health check for the API gateway.

```bash
curl https://mascarade.saillant.cc/health
```

#### `GET /health/status`

Detailed health status with uptime and version.

```bash
curl https://mascarade.saillant.cc/health/status
```

---

### AI Chat

#### `POST /v1/chat/completions`

OpenAI-compatible chat completion. Routes to the appropriate Ollama node based on model (Tower CPU for light models, KXKM-AI GPU for heavy models). RAG context is automatically injected from Qdrant + SearXNG fallback.

```bash
curl -X POST https://mascarade.saillant.cc/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral:7b",
    "messages": [{"role": "user", "content": "Design a 5V buck converter"}]
  }'
```

**Response:** OpenAI-format chat completion object.

#### `GET /v1/models`

List available models (OpenAI format).

```bash
curl https://mascarade.saillant.cc/v1/models
```

**Response:** `{ "object": "list", "data": [{ "id": "albert", ... }, { "id": "mistral:7b", ... }, ...] }`

#### `POST /api/ai/chat`

Chat endpoint for er-ops sidebar integration. Supports streaming (`stream: true` by default) and optional RAG (`rag: false` to disable).

```bash
# Non-streaming
curl -X POST https://mascarade.saillant.cc/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral:7b",
    "messages": [{"role": "user", "content": "Etat du cluster?"}],
    "stream": false
  }'

# Streaming
curl -N -X POST https://mascarade.saillant.cc/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral:7b",
    "messages": [{"role": "user", "content": "Explique le routage Ollama multi-machine"}]
  }'
```

---

### Agents

#### `GET /agents/list`

List all 242 registered agents with their metadata.

```bash
curl https://mascarade.saillant.cc/agents/list
```

**Response:** `{ "agents": [{ "name": "ops-monitor", "description": "...", ... }, ...], "count": 242 }`

#### `POST /agents/invoke`

Invoke a specific agent by name.

```bash
curl -X POST https://mascarade.saillant.cc/agents/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "ops-healthcheck",
    "input": "Verifie le service Qdrant"
  }'
```

**Production agents (9):** ops-monitor, ops-deployer, ops-incident, ops-healthcheck, ops-security, web-researcher, lead-scorer, dolibarr-assistant, grist-data.

---

### RAG Pipeline

The RAG pipeline follows: bge-m3 embeddings -> Qdrant vector search -> SearXNG web search fallback.

#### `POST /api/ai/rag/index`

Index a document into the RAG pipeline (Qdrant collection).

```bash
curl -X POST https://mascarade.saillant.cc/api/ai/rag/index \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The LM2596 is a step-down voltage regulator...",
    "source": "datasheets/lm2596",
    "metadata": {"type": "datasheet"}
  }'
```

#### `GET /api/ai/rag/stats`

Get RAG pipeline statistics (collection size, indexed documents, embedding model).

```bash
curl https://mascarade.saillant.cc/api/ai/rag/stats
```

---

### Open Buro (EU Interoperability)

#### `GET /openburo/apps`

List registered applications in the Open Buro app registry.

```bash
curl https://mascarade.saillant.cc/openburo/apps
```

#### `GET /openburo/apps/:id`

Get a specific application by ID.

```bash
curl https://mascarade.saillant.cc/openburo/apps/mascarade-core
```

#### `GET /openburo/capabilities`

List Open Buro capabilities for this instance.

```bash
curl https://mascarade.saillant.cc/openburo/capabilities
```

#### `GET /openburo/health`

Health check for all Open Buro services.

```bash
curl https://mascarade.saillant.cc/openburo/health
```

#### `POST /openburo/ai/chat`

AI chat endpoint for Open Buro integration. Same RAG pipeline as `/api/ai/chat`.

```bash
curl -X POST https://mascarade.saillant.cc/openburo/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral:7b",
    "messages": [{"role": "user", "content": "Liste les factures du mois"}]
  }'
```

#### `GET /openburo/objects/schemas`

List all business object schemas.

```bash
curl https://mascarade.saillant.cc/openburo/objects/schemas
```

#### `GET /openburo/objects/schemas/:type`

Get a specific business object schema by type.

```bash
curl https://mascarade.saillant.cc/openburo/objects/schemas/invoice
```

#### `GET /openburo/workspaces`

List workspaces.

```bash
curl https://mascarade.saillant.cc/openburo/workspaces
```

#### `POST /openburo/workspaces`

Create a workspace.

```bash
curl -X POST https://mascarade.saillant.cc/openburo/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "mon-espace", "description": "Espace de travail projet"}'
```

#### `GET /openburo/search`

Search across Open Buro resources.

```bash
curl "https://mascarade.saillant.cc/openburo/search?q=facture&type=invoice"
```

#### `POST /openburo/search/index`

Index a resource into Open Buro search.

```bash
curl -X POST https://mascarade.saillant.cc/openburo/search/index \
  -H "Content-Type: application/json" \
  -d '{"id": "doc-123", "type": "document", "content": "...", "metadata": {}}'
```

#### `GET /openburo/search/stats`

Search index statistics.

```bash
curl https://mascarade.saillant.cc/openburo/search/stats
```

#### `POST /openburo/events`

Publish a CloudEvents event to the event bus (Redis Streams).

```bash
curl -X POST https://mascarade.saillant.cc/openburo/events \
  -H "Content-Type: application/json" \
  -d '{"type": "invoice.created", "source": "dolibarr", "data": {"id": 42}}'
```

#### `GET /openburo/events`

List recent events from the event bus.

```bash
curl https://mascarade.saillant.cc/openburo/events
```

#### `GET /openburo/events/stats`

Event bus statistics.

```bash
curl https://mascarade.saillant.cc/openburo/events/stats
```

#### `POST /openburo/notifications`

Send a notification through Open Buro.

```bash
curl -X POST https://mascarade.saillant.cc/openburo/notifications \
  -H "Content-Type: application/json" \
  -d '{"title": "Alerte", "body": "Service down", "priority": "high"}'
```

#### Connectors

```bash
# Grist webhook
curl -X POST https://mascarade.saillant.cc/openburo/connectors/grist/webhook \
  -H "Content-Type: application/json" -d '{}'

# Dolibarr webhook
curl -X POST https://mascarade.saillant.cc/openburo/connectors/dolibarr/webhook \
  -H "Content-Type: application/json" -d '{}'

# n8n webhook
curl -X POST https://mascarade.saillant.cc/openburo/connectors/n8n/webhook \
  -H "Content-Type: application/json" -d '{}'

# Connectors status
curl https://mascarade.saillant.cc/openburo/connectors/status
```

---

## Authenticated Endpoints (Bearer token required)

These routes require `Authorization: Bearer <token>` unless `MASCARADE_ALLOW_PUBLIC_API=true` is set in the environment.

### Agents CRUD

```bash
# List agents
curl https://mascarade.saillant.cc/api/agents \
  -H "Authorization: Bearer $TOKEN"

# Agent catalog
curl https://mascarade.saillant.cc/api/agents/catalog \
  -H "Authorization: Bearer $TOKEN"

# Create agent
curl -X POST https://mascarade.saillant.cc/api/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent", "system_prompt": "You are...", "model": "mistral:7b"}'

# Run agent
curl -X POST https://mascarade.saillant.cc/api/agents/ops-monitor/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Status report"}]}'

# Get agent
curl https://mascarade.saillant.cc/api/agents/ops-monitor \
  -H "Authorization: Bearer $TOKEN"

# Update agent
curl -X PUT https://mascarade.saillant.cc/api/agents/ops-monitor \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"system_prompt": "Updated prompt..."}'

# Delete agent
curl -X DELETE https://mascarade.saillant.cc/api/agents/ops-monitor \
  -H "Authorization: Bearer $TOKEN"

# Agent metrics
curl https://mascarade.saillant.cc/api/agents/ops-monitor/metrics \
  -H "Authorization: Bearer $TOKEN"
```

### Providers

```bash
# List providers
curl https://mascarade.saillant.cc/api/agents/providers \
  -H "Authorization: Bearer $TOKEN"

# Provider status
curl https://mascarade.saillant.cc/api/agents/providers/status \
  -H "Authorization: Bearer $TOKEN"

# Update provider key
curl -X PUT https://mascarade.saillant.cc/api/agents/providers/mistral/key \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key": "new-api-key"}'
```

### Metrics & Cache

```bash
# Global metrics
curl https://mascarade.saillant.cc/api/agents/metrics \
  -H "Authorization: Bearer $TOKEN"

# Cache stats
curl https://mascarade.saillant.cc/api/agents/cache/stats \
  -H "Authorization: Bearer $TOKEN"

# Load balancer stats
curl https://mascarade.saillant.cc/api/agents/load-balancer/stats \
  -H "Authorization: Bearer $TOKEN"

# Fallback stats
curl https://mascarade.saillant.cc/api/agents/fallback/stats \
  -H "Authorization: Bearer $TOKEN"
```

### Orchestration

```bash
# Send message to agent
curl -X POST https://mascarade.saillant.cc/api/agents/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"agent": "lead-scorer", "message": "Score this lead: ..."}'

# Orchestrate multi-agent task
curl -X POST https://mascarade.saillant.cc/api/agents/orchestrate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task": "Audit de securite complet", "agents": ["ops-security", "ops-healthcheck"]}'
```

---

## Core Engine Endpoints (port 8100, internal)

These are exposed on the Python FastAPI core, accessible only internally or via the API gateway proxy.

### Health & System

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | Health check |
| GET | `/v1/version` | API version |
| GET | `/v1/models` | Available models |
| GET | `/health/providers` | Provider health metrics |
| GET | `/metrics` | Prometheus metrics |

### Authentication

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/v1/api-keys` | Add API key |
| POST | `/v1/api-keys/remove` | Remove API key |
| GET | `/v1/api-keys` | List API keys |

### Chat

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/chat/completions` | OpenAI-compatible chat completion |

### Agents

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/agents` | List agents |
| POST | `/api/agents` | Create agent |
| GET | `/api/agents/{name}` | Get agent |
| PUT | `/api/agents/{name}` | Update agent |
| DELETE | `/api/agents/{name}` | Delete agent |
| POST | `/api/agents/{name}/run` | Run agent |
| GET | `/api/agents/{name}/metrics` | Agent metrics |

### RAG Pipeline

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/v1/api/rag/query` | RAG query |
| POST | `/v1/api/rag/ingest` | Ingest document |
| POST | `/v1/api/rag/ingest/url` | Ingest from URL |
| POST | `/v1/api/rag/ingest/upload` | Ingest uploaded file |
| GET | `/v1/api/rag/collections` | List collections |
| GET | `/v1/api/rag/collections/{name}` | Collection info |
| DELETE | `/v1/api/rag/collections/{name}` | Delete collection |
| POST | `/v1/api/rag/search` | Semantic search |
| POST | `/v1/api/rag/eval` | RAG evaluation |

### Cluster / P2P

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/v1/cluster/identity` | Node identity |
| GET | `/v1/cluster/peers` | List peers |
| POST | `/v1/cluster/forward/send` | Forward to peer |
| GET | `/v1/cluster/p2p/status` | P2P mesh status |
| GET | `/v1/cluster/p2p/topology` | Network topology |
| GET | `/v1/cluster/p2p/peers` | Peer details |
| POST | `/v1/cluster/p2p/task` | Submit distributed task |
| GET | `/v1/cluster/p2p/stream` | SSE event stream |

### Providers

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/providers` | List providers |
| GET | `/api/providers/status` | Provider status |
| PUT | `/api/providers/{name}/key` | Update provider key |
| POST | `/api/providers/codestral/fim` | Codestral fill-in-the-middle |

### Node Engine

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/v1/graph/graphs/{id}/execute` | Execute graph |
| POST | `/v1/graph/graphs/execute-inline` | Execute inline graph |
| GET | `/v1/graph/runtime/status` | Runtime status |

### Fine-tuning

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/finetune/jobs` | Create fine-tune job |
| GET | `/finetune/jobs` | List jobs |
| GET | `/finetune/jobs/{id}` | Job status |
| PUT | `/finetune/jobs/{id}` | Update job |
| DELETE | `/finetune/jobs/{id}` | Delete job |

### Other Modules

| Module | Prefix | Description |
| ------ | ------ | ----------- |
| Skills | `/api/skills/*` | Skill management and assignment |
| Eval | `/v1/eval/*` | Benchmark evaluation runs |
| KiCad MCP | `/v1/mcp/kicad/*` | KiCad analysis, DRC, SPICE |
| CAD MCP | `/v1/mcp/*` | FreeCAD, OpenSCAD, toolpath |
| Mistral Studio | `/v1/mistral-studio/*` | Mistral fine-tuning jobs |
| Mistral Agents | `/v1/mistral-agents/*` | Mistral agent discovery/run |
| Scheduler | `/v1/scheduler/*` | GPU-aware worker scheduling |
| Voice | `/v1/voice/*` | Voice pipeline (STT/TTS) |
| Audio | `/v1/audio/*` | OpenAI-compatible audio (transcription, speech) |
| Graph (StateGraph) | `/v1/graph/*` | LangGraph-inspired state graph execution |
| Analytics | `/v1/analytics/*` | Benchmark analytics |
| Memory | `/api/memory/*` | Mem0 memory service |
| ComfyUI | `/api/comfyui/*` | ComfyUI image generation proxy |
| CAD | `/api/cad/*` | FreeCAD document management |

---

## Interactive Documentation

When running locally, the Core Engine provides auto-generated docs:

- **Swagger UI**: http://localhost:8100/docs
- **ReDoc**: http://localhost:8100/redoc
- **OpenAPI Spec**: http://localhost:8100/openapi.json

---

*Generated from router source files -- 2026-03-27*
