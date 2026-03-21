# Mascarade Core API Documentation

**Version:** 0.1.0

Personal agentic orchestration system - Python core API

Provides LLM routing, agent orchestration, memory management, and OpenAI-compatible chat completions.

## Base URL

```
http://localhost:8100
```

## Endpoints

### Health

#### `GET /health`

Health check endpoint - returns basic system status.

---

#### `GET /v1/version`

Version endpoint - returns API version and service information.

---

#### `GET /health/providers`

Provider health metrics endpoint - returns detailed health statistics for all providers.

---

### Authentication

#### `POST /v1/api-keys`

Add a new API key to the active keys list.

---

#### `POST /v1/api-keys/remove`

Remove an API key from the active keys list.

---

#### `GET /v1/api-keys`

List all active API keys (with partial masking for security).

---

### Chat Completions

#### `POST /chat/completions`

Create a chat completion (OpenAI-compatible endpoint). This is a frozen API contract that follows the OpenAI API specification. Any changes to this endpoint should maintain backward compatibility.

---

### Agents

#### `POST /api/agents`

Create a new agent with the specified configuration.

---

#### `GET /api/agents`

List all registered agents in the system.

---

#### `GET /api/agents/{name}`

Get a specific agent by name.

---

#### `PUT /api/agents/{name}`

Update an existing agent's configuration. This endpoint supports prompt versioning - when the system_prompt is changed, a new version is automatically created and tracked.

---

#### `DELETE /api/agents/{name}`

Delete an agent from the registry.

---

#### `POST /api/agents/{name}/run`

Run an agent with the provided messages.

---

#### `GET /api/agents/{name}/metrics`

Get metrics for a specific agent.

---

### Memory

#### `GET /api/memory/status`

Get Mem0 memory service status. Returns basic status information about the Mem0 integration. This endpoint will be expanded to include actual Mem0 service health checks.

---

### Providers

#### `GET /api/providers`

List all available LLM providers in the system.

---

#### `GET /api/providers/status`

Get status and configuration details for all providers.

---

#### `PUT /api/providers/{name}/key`

Update API keys for a specific provider.

---

#### `GET /api/providers/bedrock/models`

List AWS Bedrock models including fine-tuned custom models.

---

#### `GET /api/providers/bedrock/finetune-jobs`

Check status of AWS Bedrock fine-tuning jobs.

---

## Additional Information

### Interactive Documentation

For complete API documentation with request/response schemas and interactive testing:

- **Swagger UI**: http://localhost:8100/docs
- **ReDoc**: http://localhost:8100/redoc
- **OpenAPI Spec**: http://localhost:8100/openapi.json

### Authentication

Most endpoints require authentication. Include your API key in the request headers:

```
Authorization: Bearer <your-api-key>
```

### Key Features

- **LLM Provider Routing**: Intelligent routing to multiple LLM providers (OpenAI, Anthropic, Mistral, etc.)
- **Agent Orchestration**: Create and manage specialized AI agents with custom prompts and capabilities
- **Memory Layer**: Persistent conversation memory via Mem0 integration
- **OpenAI Compatibility**: Drop-in replacement for OpenAI API endpoints
- **Health Monitoring**: Real-time provider health checks and failover

---

*Generated automatically from router source files*