# Mascarade Cockpit Frontend Spec

## Product

Mascarade Cockpit is the single operator UI for the local Mascarade stack.

Primary goals:
- inspect runtime health quickly
- test prompts and agents
- run multi-agent orchestration
- observe service incidents and inter-agent traces without leaving the cockpit

Non-goals:
- marketing site
- generic analytics portal
- second standalone ops frontend competing with the cockpit

## Visual Direction

The cockpit keeps the Matrix/CRT language already established in `web/src/index.css`.

Required traits:
- dark layered background
- subtle grid and scanline feel
- amber/green signal palette
- monospace typography
- visible keyboard focus states

This look is part of the product identity, not optional decoration.

## Information Architecture

Routes and order:
1. `/` Dashboard
2. `/playground` Playground
3. `/agents` Agents
4. `/orchestrate` Orchestrate
5. `/logs` Logs
6. `/metrics` Metrics
7. `/infra` Infrastructure
8. `/knowledge-base` Knowledge Browser
9. `/comfyui` ComfyUI

Groups:
- Core: Dashboard, Playground, Agents, Orchestrate
- Operations: Logs, Metrics, Infrastructure
- Integrations: Knowledge Base, ComfyUI

Mobile dock:
- Home
- Lab
- Agents
- Logs
- Menu

Keyboard shortcuts:
- `Alt+1..9` follow the route order above

## Shell Contract

Global shell behavior:
- desktop sidebar + mobile drawer
- mobile dock for primary lanes
- top bar with page identity and runtime quick links
- session/auth panel remains keyboard-safe
- skip link remains available
- dialogs and panels lock global shortcuts while open

## Agent Zero Contract

`agent-zero` is the lead workflow entry for ambiguous requests and incident framing.

Recommended use:
- clarify a vague request
- produce a short plan
- identify risks and next action
- frame an incident before dispatching specialists

UI obligations:
- visible from Dashboard
- visible from Logs when a run or incident looks suspicious
- first-class in Agents and Orchestrate

## Page Contracts

### Dashboard
Purpose:
- runtime overview
- quick launch into the main lanes

Must show:
- gateway posture
- provider bus summary
- entry points to `agent-zero`, Playground, Metrics, Logs, Infrastructure

### Playground
Purpose:
- prompt sandbox
- provider/model output inspection

Must show:
- direct prompt interaction
- payload visibility
- easy path toward `agent-zero`

### Agents
Purpose:
- registry and detail entry

Must show:
- `agent-zero` first
- fast scan of the registry
- clear path to Agent Detail

### Orchestrate
Purpose:
- dispatch one request across multiple agents
- inspect final results and live run trace

Must show:
- armed cluster
- prompt lane
- final orchestration results
- `run_id`
- structured live trace for the current run

### Logs
Purpose:
- unified live observability lane

Current sources in v1:
- native inter-agent traces
- consolidated service incidents from `/api/ops/monitor`

Future complementary sources:
- Loki history
- OTel-backed telemetry
- host-level collection
- optional AgentSight presence signal

Must show:
- live feed controls
- filters by source, severity, run, agent, event type
- run detail lane
- handoffs between agents
- CTA toward `agent-zero`

### Metrics
Purpose:
- health and latency posture

Must show:
- gateway state
- service table
- alert lane
- direct path to Logs and `agent-zero`

### Infrastructure
Purpose:
- raw stack map and exposed endpoints

Must show:
- gateway health
- provider list
- observed service grid
- direct path to Logs

### Knowledge Browser
Purpose:
- browse and update knowledge-base-backed content

### ComfyUI
Purpose:
- inspect image generation pipeline and outputs

## Data Contracts

### Orchestration response
`POST /api/agents/orchestrate`

Returns:
- `run_id`
- `mode`
- `results[]`

`run_id` is the main correlation id for orchestration observability.

### Trace events
Structured trace events include:
- `run_started`
- `step_started`
- `agent_input`
- `agent_output`
- `handoff`
- `run_completed`
- `run_failed`

Fields of interest:
- `run_id`
- `ts`
- `agent_name`
- `from_agent`
- `to_agent`
- `event_type`
- `prompt_excerpt`
- `content_excerpt`
- `provider`
- `model`
- `error`

### Ops logs feed
`/api/ops/logs/recent` returns normalized entries used by the Logs page.

Current entry sources:
- `agent-trace`
- `service`

## Accessibility

Required:
- visible focus states
- keyboard navigation across shell and filters
- no hidden critical action behind pointer-only interaction
- dialogs remain focus-managed
- skip link remains functional

## Observability Rollout

### Implemented in this repo now
- native core orchestration tracing
- `run_id` surfaced through API and frontend
- Logs page for live trace/service incident reading
- Orchestrate page live trace panel

### Complement planned and scaffolded
- Loki
- Promtail
- OpenTelemetry Collector
- optional AgentSight complement

### Not yet wired end-to-end
- full host machine live logs in cockpit
- Loki history query UI
- OTel exporters from core and API
- AgentSight runtime integration beyond presence/documentation

## Acceptance Criteria

The feature is acceptable when:
- every orchestration run exposes a `run_id`
- inter-agent exchanges are visible in the cockpit
- Logs page can filter traces by run and agent
- Orchestrate shows the trace of the current run
- Dashboard, Metrics and Infrastructure can all open the Logs lane
- the Matrix/CRT visual direction remains intact
