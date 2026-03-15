# API -> Core -> Providers -> Observability — Sequence Diagram — 2026-03-11

## Scope

Ce document fixe le chemin d'execution principal entre:

- la facade HTTP `api/` (Hono)
- le core Python `core/mascarade/server.py` (FastAPI)
- le routeur providers `core/mascarade/router/router.py`
- la surface d'observabilite runtime (`agent traces`, OTLP logs, metrics)

References code:

- `api/src/routes/agents.ts`
- `api/src/client/core.ts`
- `core/mascarade/server.py`
- `core/mascarade/router/router.py`
- `core/mascarade/orchestrator/engine.py`
- `core/mascarade/observability/agent_trace.py`

## Main runtime sequence

```mermaid
sequenceDiagram
    autonumber
    participant U as Client / UI / curl
    participant A as API Hono (:3100)
    participant C as coreClient
    participant S as Core FastAPI (:8100)
    participant O as Orchestrator
    participant R as Router
    participant CA as ResponseCache
    participant LB as LoadBalancer
    participant FB as FallbackState
    participant P as Selected Provider
    participant T as AgentTraceBuffer
    participant L as OTLP / Logs / Langfuse-Grafana lane

    alt Simple request via POST /api/agents/send
        U->>A: POST /api/agents/send
        A->>C: coreClient.send(body)
        C->>S: POST /send + Authorization
        S->>R: router.send(messages, strategy, provider, model, ...)
        R->>CA: retrieve(...)
        alt Cache hit
            CA-->>R: cached response
            R-->>S: LLMResponse
            S-->>C: content + model + provider + usage
            C-->>A: normalized JSON
            A-->>U: 200 response
        else Cache miss
            R->>FB: build_sequence(strategy, provider, available_providers)
            loop fallback attempts
                R->>LB: select_provider(...) + request_started(...)
                R->>P: send(messages, model, system, temperature, ...)
                alt provider failure
                    P-->>R: exception
                    R->>LB: request_completed(success=false)
                    R->>FB: record_failure(provider)
                    R->>R: continue next fallback attempt
                else provider success
                    P-->>R: LLMResponse
                    R->>LB: request_completed(success=true)
                    R->>R: metrics.track_request(...)
                    opt non-strict provider path
                        R->>CA: store(response, provider_used, model, ttl, ...)
                    end
                    R-->>S: LLMResponse
                    S-->>C: content + model + provider + usage
                    C-->>A: normalized JSON
                    A-->>U: 200 response
                end
            end
        end
    else Multi-agent request via POST /api/agents/orchestrate
        U->>A: POST /api/agents/orchestrate
        A->>C: coreClient.orchestrate(body)
        C->>S: POST /orchestrate + Authorization
        S->>O: orchestrator.run(agent_names, prompt, mode, routing_overrides)
        O->>T: record(run_started)
        loop each agent / step
            O->>T: record(step_started / agent_input)
            O->>R: router.send(...) or cluster.forward_send(...)
            R->>CA: retrieve(...)
            alt cache miss or remote route
                R->>FB: build_sequence(...)
                R->>LB: select_provider(...) + request_started(...)
                R->>P: send(...)
                P-->>R: LLMResponse or error
                R->>LB: request_completed(...)
                R->>R: metrics.track_request(...)
                opt local non-strict success
                    R->>CA: store(...)
                end
            end
            O->>T: record(agent_output / handoff / run_failed)
        end
        O->>T: record(run_completed)
        T->>L: print JSON structured log + schedule_otlp_log(...)
        S-->>C: run_id + per-step results
        C-->>A: normalized JSON
        A->>L: emitStructuredLog(orchestrate_completed)
        A-->>U: 200 response with run_id
    end
```

## Observability read paths

```mermaid
sequenceDiagram
    autonumber
    participant UI as Operator UI / curl
    participant API as API Hono (:3100)
    participant Core as Core FastAPI (:8100)
    participant Trace as AgentTraceBuffer
    participant Prom as Prometheus scrape

    UI->>API: GET /api/agents/metrics | /cache/stats | /fallback/stats
    API->>Core: proxy authenticated request
    Core-->>API: router metrics summary
    API-->>UI: operator JSON

    UI->>Core: GET /agent-traces/recent | /agent-traces/{run_id}
    Core->>Trace: recent(...) / run_events(...)
    Trace-->>Core: structured trace events
    Core-->>UI: trace JSON / SSE

    Prom->>Core: GET /metrics
    Core-->>Prom: Prometheus exposition format
```

## Notes

- `api/` reste une facade: elle valide peu, relaie vers `core`, et ajoute une couche de journalisation operateur.
- `core` porte la logique de routage, de fallback, de cache, de load balancing et la plupart des traces d'execution.
- `AgentTraceBuffer` ne sert pas seulement la consultation `recent/run_id`; il emet aussi des logs structures et planifie un export OTLP.
- `POST /v1/chat/completions` sur le core suit pratiquement la meme branche que `POST /send`, avec une adaptation OpenAI-compatible en entree/sortie.
- les stats `metrics/cache/load-balancer/fallback` sont des vues de controle du routeur, pas une trace causale complete d'un run.
