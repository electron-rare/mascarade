# Open Source Landscape — Mascarade Competitors & Libraries

_Audit: 2026-03-25_

## Top Integration Priorities

| # | Project | Stars | Why | Effort |
|---|---------|-------|-----|--------|
| 1 | **LiteLLM** `BerriAI/litellm` | 40K | Replace 25+ provider impls with single abstraction | HIGH |
| 2 | **Langfuse** `langfuse/langfuse` | 24K | Self-hosted observability (traces, costs, evals) | LOW |
| 3 | **python-a2a** `themanojdesai/python-a2a` | 1K | Standardize A2A on Google protocol | MEDIUM |
| 4 | **RouteLLM** `lm-sys/RouteLLM` | 5K | ML-based routing (already referenced) | LOW |
| 5 | **MCP Python SDK** `modelcontextprotocol/python-sdk` | 22K | Official SDK for MCP client/server | MEDIUM |
| 6 | **kicad-mcp-python** `Finerestaurant/kicad-mcp-python` | 33 | MCP server for KiCad IPC API | LOW |
| 7 | **GPTCache** `zilliztech/GPTCache` | 8K | Semantic cache for multi-tier cache upgrade | MEDIUM |
| 8 | **OpenLLMetry** `traceloop/openllmetry` | 7K | Drop-in OTel instrumentation for Python | LOW |

## LLM Orchestration / Router

| Project | Stars | Overlap | Integration |
|---------|-------|---------|-------------|
| LiteLLM `BerriAI/litellm` | 40K | Gateway/proxy | Replace provider layer |
| Portkey `Portkey-AI/gateway` | 11K | Fast AI Gateway | Alternative to LiteLLM |
| RouteLLM `lm-sys/RouteLLM` | 5K | ML routing | Routing strategy plugin |
| Plano `katanemo/plano` | 6K | Routing + agents | Competitor, study patterns |

## Agent Frameworks

| Project | Stars | Overlap | Integration |
|---------|-------|---------|-------------|
| AutoGen `microsoft/autogen` | 56K | Multi-agent conversations | Host as provider/runtime |
| CrewAI `crewAIInc/crewAI` | 47K | Role-playing agents | Register crews as agents |
| LangGraph `langchain-ai/langgraph` | 27K | Agent graphs/DAG | Complement Node Engine |
| Symphony `GradientHQ/symphony` | 32 | Decentralized P2P agents | Study P2P patterns |

## A2A Protocol

| Project | Stars | Integration |
|---------|-------|-------------|
| Google A2A `google/A2A` | 5K+ | Track spec, implement |
| python-a2a `themanojdesai/python-a2a` | 1K | Replace custom A2A code |
| A2A-MCP-Server `GongRzhe/A2A-MCP-Server` | 145 | Bridge MCP ↔ A2A |

## MCP Ecosystem

| Project | Stars | Integration |
|---------|-------|-------------|
| MCP Servers `modelcontextprotocol/servers` | 82K | Reference + consume |
| MCP Python SDK `modelcontextprotocol/python-sdk` | 22K | Dependency for MCP |
| MCP Registry `modelcontextprotocol/registry` | 7K | Discover/register servers |

## Hardware / CAD AI

| Project | Stars | Integration |
|---------|-------|-------------|
| kicad-happy `aklofas/kicad-happy` | 96 | Port skills to agents |
| kicad-mcp-python `Finerestaurant/kicad-mcp-python` | 33 | MCP server for KiCad IPC |
| Seeed kicad-mcp `Seeed-Studio/kicad-mcp-server` | 23 | Alternative KiCad MCP |
| pcb-designer-ai `assalas/pcb-designer-ai-agent` | 35 | ML placement/routing |

## Observability

| Project | Stars | Integration |
|---------|-------|-------------|
| Langfuse `langfuse/langfuse` | 24K | Self-hosted LLM observability |
| OpenLLMetry `traceloop/openllmetry` | 7K | OTel auto-instrumentation |
| OpenLIT `openlit/openlit` | 2K | OTel + GPU monitoring |
| Pydantic Logfire `pydantic/logfire` | 4K | Pydantic-native observability |

## Semantic Caching

| Project | Stars | Integration |
|---------|-------|-------------|
| GPTCache `zilliztech/GPTCache` | 8K | Upgrade L3 cache |
| Upstash Semantic Cache `upstash/semantic-cache` | 294 | Serverless semantic cache |
