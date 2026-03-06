# Observability Architecture

## Goal

Mascarade observability is split into a product layer and complementary infrastructure.

Product layer:
- native orchestration tracing inside Mascarade
- gateway-level health and service incidents
- cockpit views for live inspection

Complementary infrastructure:
- OpenTelemetry Collector
- Loki
- Promtail
- optional AgentSight side channel

## Current Implemented Layer

### Native tracing
The core now emits structured orchestration events with a stable `run_id`.

Event types:
- `run_started`
- `step_started`
- `agent_input`
- `agent_output`
- `handoff`
- `run_completed`
- `run_failed`

Storage model:
- in-memory recent buffer inside the core
- filtered access by `run_id`, `agent_name`, `event_type`

Routes exposed by the core:
- `GET /agent-traces/recent`
- `GET /agent-traces/{run_id}`
- `GET /agent-traces/stream`

### Gateway facade
The API exposes:
- `GET /api/ops/monitor`
- `GET /api/ops/summary`
- `GET /api/ops/sources`
- `GET /api/ops/logs/recent`
- `GET /api/ops/agent-traces/recent`
- `GET /api/ops/agent-traces/:runId`

Current logs feed is a normalized blend of:
- native agent traces
- service incidents derived from health probes

## Complementary Stack

### Loki
Role:
- store log and trace history
- support future history queries from the cockpit

Scaffolded assets:
- `deploy/loki/loki-config.yaml`
- `scripts/modules/loki.sh`

### Promtail
Role:
- ship Docker and journald logs to Loki

Scaffolded assets:
- `deploy/promtail/promtail-config.yaml`
- `scripts/modules/promtail.sh`

### OpenTelemetry Collector
Role:
- receive OTLP traces/logs/metrics
- become the standard convergence point for future core/API exporters

Scaffolded assets:
- `deploy/otel-collector/config.yaml`
- `scripts/modules/otel-collector.sh`

Current state:
- collector is scaffolded with OTLP receivers and debug exporter
- exporters from core/API are not wired yet

### AgentSight
Role:
- optional external audit tool for Linux/eBPF investigation
- never a hard dependency of the cockpit

Current state:
- documented as complement only
- exposed in `/api/ops/sources` as pending/optional

## Deployment Notes

The new observability services are opt-in.
They are not part of the default profiles yet, to avoid destabilizing standard installs.

Available service ids for `./setup --with ...`:
- `loki`
- `promtail`
- `otel-collector`

Example:
```bash
./setup --with core,api,ops-console,loki,promtail,otel-collector --yes
```

## Next Steps

1. Add OTLP exporters in core and API.
2. Add Loki-backed history endpoints and UI.
3. Add host-level live logs collection for machine events.
4. Add optional AgentSight health/presence integration.
