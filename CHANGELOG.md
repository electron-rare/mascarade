# Changelog

All notable changes to the Mascarade API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## API Version 1.0.0 - Initial Release

### Overview
This release establishes the baseline API contract for Mascarade. All endpoints are now versioned under `/v1/` prefix to ensure backward compatibility and stability guarantees.

### Added - Non-Breaking
- **Versioning Infrastructure**
  - All API endpoints now use `/v1/` prefix for versioning
  - New `GET /v1/version` endpoint returns API version, supported features, and provider list
  - Python API version module (`mascarade.api_version`) with programmatic access to version metadata
  - Deprecation middleware infrastructure (RFC 8594-compliant) for future endpoint deprecations
    - Supports `Deprecation`, `Warning`, `Sunset`, `Link`, and `X-Deprecated-Since` headers
    - Pattern-based and endpoint-specific deprecation rules
  - Comprehensive regression test suite (45+ tests) to ensure API stability across releases

- **Core Python API (port 8100)**
  - `GET /v1/version` - API version metadata and supported features
  - `POST /v1/chat/completions` - OpenAI-compatible endpoint (frozen contract)
  - `POST /v1/agents/send` - Primary agent dispatch endpoint
  - `POST /v1/agents/orchestrate` - Multi-agent orchestration
  - `GET /v1/agents/providers` - List active LLM providers
  - `GET /v1/agents/metrics` - Global metrics and statistics
  - `GET /v1/cache/stats` - Cache performance metrics
  - `/v1/cluster/*` - Multi-node coordination endpoints
  - `/v1/knowledge-base/*` - Knowledge base operations
  - `/v1/api-keys/*` - API key management endpoints

- **TypeScript API (port 3100)**
  - `GET /v1/version` - API version metadata aggregated from core service
  - `/v1/api/agents/*` - Agent management and execution
  - `/v1/api/cluster/*` - Cluster coordination proxy
  - `/v1/api/cad/*` - CAD/EDA integration endpoints
  - `/v1/api/comfyui/*` - ComfyUI workflow integration
  - `/v1/api/knowledge-base/*` - Knowledge base operations
  - `/v1/api/ops/*` - Operations and monitoring
  - `/v1/api/industrial/*` - Industrial automation endpoints
  - `/v1/api/mcp/industrial/*` - MCP industrial integration
  - `/health` - Health check (no version prefix, always stable)

### Stability Guarantees

#### Frozen Contracts
The following endpoints have frozen contracts and will not change in v1.x:
- `POST /v1/chat/completions` - OpenAI-compatible interface
  - Request/response schema matches OpenAI API v1
  - Supports: messages, model, temperature, max_tokens, stream
  - Response includes: id, object, created, choices, usage

#### Backward Compatibility Promise
- No breaking changes will be introduced in v1.x releases
- New fields may be added to responses (clients should ignore unknown fields)
- Optional request parameters may be added
- Deprecated features will be supported for minimum 6 months with warnings
- Migration guide will be provided before any v2.0 breaking changes

### Breaking Changes
- **[BREAKING]** None - this is the initial versioned release establishing the baseline API contract
  - Note: This release establishes `/v1/` as the canonical API prefix. Non-versioned paths are no longer supported.
  - Clients must update to use `/v1/` prefixed endpoints (Python core) and `/v1/api/` prefixed endpoints (TypeScript API).
  - Migration path: Replace `/agents/*` with `/v1/agents/*` and `/api/*` with `/v1/api/*`

### Deprecated
- None

### Security
- **[SECURITY]** All protected endpoints require `Authorization: Bearer <token>` header
- `/health` endpoint remains public for monitoring purposes
- API key management available via `/v1/api-keys/*` endpoints

---

## Version History

### [Unreleased] - 2026-03-24

#### Added
- **Agent Gates** — Pre/post execution gate system with 4 built-in checks (`has_system_prompt`, `has_skills`, `has_tools`, `is_configured`). Required and optional gates, `EvidenceRecord` for audit trails. (`core/mascarade/agents/base.py`)
- **MCP n8n Client** — `N8nMcpClient` with 4 tools: `list_workflows`, `execute_workflow`, `get_execution`, `list_executions`. Auto-registered via `N8N_BASE_URL` env var. (`core/mascarade/mcp/n8n.py`)
- **MCP ERPNext Client** — `ERPNextMcpClient` with 6 tools: `list_leads`, `get_lead`, `create_lead`, `list_quotations`, `create_quotation`, `list_invoices`. Auto-registered via `FRAPPE_URL` env var. (`core/mascarade/mcp/erpnext.py`)
- **A2A SDK migration (Phase 1)** — Router aligned to A2A spec v0.3 with 6 task states (`submitted`, `working`, `input-required`, `completed`, `failed`, `canceled`), `AgentCardResponse` model, conditional `a2a-sdk` import. (`core/mascarade/routers/a2a.py`)
- **Zod validation** — 6 new schemas (`UserCreate`, `UserUpdate`, `ApiKeyCreate`, `WorkflowRun`, `FinetuneRun`, `ClusterForwardSend`) wired into 5 API routes via `validate()` middleware. (`api/src/validation/schemas.ts`)
- **Tests** — +107 new tests: 4 providers (Claude, OpenAI, LiteLLM, Bedrock), 4 routers (Admin, WebSocket, Analytics, Voice), agent gates (17 tests), MCP clients (21 tests)
- **CI** — Added TypeScript type-check step (`tsc --noEmit`) and pytest coverage threshold (`--cov-fail-under=50`)

#### Fixed
- Syntax error in `gpt53_codex.py` where `import json` was placed before the docstring

---

## Change Classification

Changes are labeled as:
- **[BREAKING]** - Requires client code changes
- **[DEPRECATED]** - Will be removed in future version
- **[ADDED]** - New feature or endpoint
- **[CHANGED]** - Modification to existing feature
- **[FIXED]** - Bug fix
- **[SECURITY]** - Security-related change

## Migration Guides

### Future v1.x → v2.0
Migration documentation will be provided when v2.0 planning begins.
