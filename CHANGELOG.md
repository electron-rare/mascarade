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

### [Unreleased]
- No changes pending

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
