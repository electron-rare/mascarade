# Mascarade Architecture

> Last updated: 2026-03-25

## 1. System Overview — Ecosystem

Mascarade is a personal agentic LLM orchestration platform spanning three core repositories and two supporting repos.

```mermaid
graph TB
    subgraph Clients
        CLI[CLI / curl]
        CL[crazy_life<br/>React 19 Cockpit]
        MC[mascarade-cockpit<br/>SvelteKit Ops Console]
    end

    subgraph mascarade["mascarade (this repo)"]
        API["api/<br/>Hono TypeScript<br/>:3100"]
        CORE["core/<br/>FastAPI Python<br/>:8100"]
        WEB["web/<br/>React 19 Bridge UI"]
        FT["finetune/<br/>Training Pipeline"]
        DEPLOY["deploy/<br/>Docker + Observability"]
    end

    subgraph KillLIFE["Kill_LIFE"]
        MCP1[kicad MCP Server]
        MCP2[freecad MCP Server]
        MCP3[openscad MCP Server]
        MCP4[validate-specs MCP]
        MCP5[knowledge-base MCP]
        MCP6[github-dispatch MCP]
        MCP7[huggingface MCP]
    end

    subgraph Providers["LLM Providers (25+)"]
        Claude[Claude / Anthropic]
        GPT[OpenAI / GPT]
        Mistral[Mistral AI]
        Bedrock[AWS Bedrock]
        Gemini[Google Gemini]
        HF[Hugging Face]
        Ollama[Ollama Local]
        LlamaCpp[llama.cpp]
        CoreML[Apple CoreML]
        MLX[MLX-LM]
        Exo[Exo Cluster]
        AppleFM[Apple FM]
        Copilot[GitHub Copilot]
        Codestral[Codestral]
        MistralAgents[Mistral Agents]
        MistralStudio[Mistral Studio]
        CodyGW[Cody Gateway]
    end

    subgraph Infra["Infrastructure Services"]
        Redis[(Redis)]
        PG[(PostgreSQL)]
        Qdrant[(Qdrant)]
        CH[(ClickHouse)]
        Neo4j[(Neo4j)]
        Graphiti[Graphiti MCP]
    end

    CLI --> API
    CL --> API
    MC --> API
    API --> CORE
    CORE --> Providers
    CORE -->|MCP Client| KillLIFE
    CORE --> Infra
    FT -->|models| Ollama
    CORE -->|P2P mesh| P2P((P2P Mesh<br/>4 nodes))
```

## 2. Core Architecture — Layers and Modules

```mermaid
graph TB
    subgraph API_Layer["API Layer — TypeScript (Hono, :3100)"]
        AUTH_MW[Auth Middleware<br/>JWT + API Key]
        RATE[Rate Limiter]
        ROUTES[33 Route Modules]
    end

    subgraph Core_Layer["Core Layer — Python (FastAPI, :8100)"]
        subgraph Router_Module["Router"]
            STRATEGY[Strategy Engine<br/>cheapest/fastest/best/specific]
            PROVIDERS[25+ Provider Adapters]
            FALLBACK[Fallback Chain]
            LB[Load Balancer]
        end

        subgraph Agent_Module["Agents"]
            REGISTRY[Agent Registry]
            KICAD_A[KiCad Agent]
            FREECAD_A[FreeCAD Agent]
            SPICE_A[SPICE Agent]
            COMP_A[Components Agent]
            SKILLS[Agent Skills]
            PROMPT_V[Prompt Versioning]
        end

        subgraph Orchestrator_Module["Orchestrator"]
            ENGINE[Orchestration Engine]
            PLAN_EXEC[Plan-and-Execute]
            TEMPLATES[Templates<br/>seq/par/pipeline]
            CB[Circuit Breaker]
            RETRY[Retry Logic]
            DLQ[Dead Letter Queue]
            CTX[Execution Context]
        end

        subgraph RAG_Module["Agentic RAG"]
            RAG_ENGINE[RAG Engine]
            RAG_RETRIEVE[Retriever]
            RAG_RERANK[Reranker]
        end

        subgraph NodeEngine_Module["Node Engine"]
            NE_ENGINE[Engine Core]
            NE_GRAPH[Graph Runtime]
            NE_EXEC[Executor]
            NE_PERSIST[Persistence]
            subgraph Workers["Workers"]
                AI_W[AI Workers]
                CAD_W[CAD Workers]
                ELEC_W[Electronics Workers]
            end
        end

        subgraph P2P_Module["P2P Mesh"]
            LIBP2P[libp2p Node]
            DHT[DHT]
            PUBSUB[PubSub / Gossip]
            RELAY[Relay]
            P2P_AUTH[Auth / Identity]
            P2P_TASKS[Task Distribution]
            DISCOVERY[mDNS Discovery]
        end

        subgraph Support["Support Services"]
            CACHE[Cache Layer]
            MCP_CLIENT[MCP Client]
            METRICS[Metrics / Prometheus]
            OBS[Observability<br/>OTEL + Langfuse]
            RBAC[RBAC / Auth]
            FINETUNE_MOD[Finetune Module]
            ANALYTICS[Analytics]
            USAGE[Usage Tracking]
            CONV[Conversation Store]
        end
    end

    API_Layer --> Core_Layer
    Router_Module --> PROVIDERS
    Agent_Module --> Router_Module
    Orchestrator_Module --> Agent_Module
    NodeEngine_Module --> Orchestrator_Module
    P2P_Module --> Router_Module
```

## 3. Request Flow — Client to Provider

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API (Hono :3100)
    participant MW as Auth Middleware
    participant Core as Core (FastAPI :8100)
    participant Router as Router
    participant Strategy as Strategy Engine
    participant Cache as Cache
    participant Provider as LLM Provider
    participant Metrics as Metrics

    C->>API: POST /v1/chat/completions
    API->>MW: Validate JWT / API Key
    MW-->>API: Authenticated
    API->>Core: Proxy POST /v1/chat/completions
    Core->>Cache: Check cache (prompt hash)
    alt Cache Hit
        Cache-->>Core: Cached response
        Core-->>API: Return cached
        API-->>C: 200 OK (cached)
    else Cache Miss
        Core->>Router: route(messages, strategy)
        Router->>Strategy: select_provider(cheapest|fastest|best|specific)
        Strategy-->>Router: Selected provider + model
        Router->>Provider: send(messages, model, params)
        alt Provider Success
            Provider-->>Router: LLM Response
            Router->>Cache: Store in cache
            Router->>Metrics: Record latency, tokens, cost
            Router-->>Core: Response
            Core-->>API: 200 OK
            API-->>C: Response
        else Provider Failure
            Provider-->>Router: Error
            Router->>Router: Fallback to next provider
            Router->>Provider: Retry with fallback
            Provider-->>Router: LLM Response
            Router-->>Core: Response (with fallback metadata)
            Core-->>API: 200 OK
            API-->>C: Response
        end
    end
```

## 4. Node Engine Execution Flow

```mermaid
flowchart TB
    subgraph Input
        GRAPH_DEF[Graph Definition<br/>JSON/YAML]
    end

    subgraph NodeEngine["Node Engine"]
        PARSER[Graph Parser]
        SCHEDULER[Scheduler]
        EXECUTOR[Executor]
        PERSIST[Persistence Layer]

        PARSER -->|parse nodes + edges| SCHEDULER
        SCHEDULER -->|topological sort| EXECUTOR
        EXECUTOR -->|save state| PERSIST
    end

    subgraph Domains["Domain Workers"]
        subgraph AI_Domain["AI Domain"]
            LLM_NODE[LLM Inference Node]
            EMBED_NODE[Embedding Node]
            CLASSIFY_NODE[Classification Node]
        end

        subgraph CAD_Domain["CAD Domain"]
            KICAD_NODE[KiCad Schematic Node]
            FREECAD_NODE[FreeCAD Model Node]
            OPENSCAD_NODE[OpenSCAD Node]
        end

        subgraph Elec_Domain["Electronics Domain"]
            SPICE_NODE[SPICE Simulation Node]
            BOM_NODE[BOM Generation Node]
            DRC_NODE[Design Rule Check Node]
        end
    end

    subgraph CrossDomain["Cross-Domain"]
        BRIDGE[Domain Bridge]
        VALIDATE[Validator]
    end

    GRAPH_DEF --> PARSER
    EXECUTOR --> AI_Domain
    EXECUTOR --> CAD_Domain
    EXECUTOR --> Elec_Domain
    EXECUTOR --> CrossDomain
    AI_Domain --> BRIDGE
    CAD_Domain --> BRIDGE
    Elec_Domain --> BRIDGE
    BRIDGE --> VALIDATE
    VALIDATE -->|feedback loop| SCHEDULER
```

## 5. P2P Mesh Topology

```mermaid
graph TB
    subgraph Mesh["P2P Mesh Network"]
        VM["VM Bootstrap Node<br/>192.168.0.119:4002<br/>Docker Host<br/>6.8GB RAM, 4 CPU"]
        GROSMAC["GrosMac (Bridge)<br/>:4001<br/>LAN ↔ Tailscale Relay<br/>100.80.178.42"]
        CILS["CILS MacBook<br/>192.168.0.210:4001<br/>Compute Worker"]
        TOWER["Tower<br/>192.168.0.120:4001<br/>Compute + Storage"]
        KXKM["KXKM-AI<br/>kxkm-ai:4001 (via relay)<br/>RTX 4090 24GB<br/>62GB RAM, 28 CPU"]
    end

    VM <-->|"gossip + DHT"| GROSMAC
    VM <-->|"gossip + DHT"| TOWER
    VM <-->|"gossip + DHT"| CILS
    GROSMAC <-->|"Tailscale relay"| KXKM
    GROSMAC <-->|"LAN"| TOWER
    GROSMAC <-->|"LAN"| CILS

    subgraph Protocols["Protocols"]
        GOSSIP[Gossip Protocol<br/>State sync]
        DHT_P[DHT<br/>Peer discovery]
        TASK_D[Task Distribution<br/>Claim-based]
        MDNS_P[mDNS<br/>Local discovery]
        STREAM[Stream Forward<br/>Request relay]
    end

    subgraph Capabilities["Node Capabilities"]
        GPU_CAP[GPU Inference<br/>KXKM-AI only]
        CPU_CAP[CPU Inference<br/>All nodes]
        STORE_CAP[Storage<br/>Tower, VM]
        FT_CAP[Fine-tuning<br/>KXKM-AI RTX 4090]
    end

    Mesh --> Protocols
    Mesh --> Capabilities
```

## 6. Fine-Tuning Pipeline Flow

```mermaid
flowchart LR
    subgraph DataPrep["Phase 1 — Data Preparation"]
        DS_BOOT[dataset_bootstrap.py<br/>13 domains, ~74k examples]
        DS_QUAL[dataset_quality.py<br/>Quality filters]
        DS_REFRESH[dataset_refresh.py<br/>Refresh from sources]
        HF_DS[HuggingFace Datasets<br/>mascarade-datasets repo]

        DS_BOOT --> DS_QUAL --> DS_REFRESH --> HF_DS
    end

    subgraph Training["Phase 2 — Training"]
        DISTILL[distill_dataset.py<br/>Teacher distillation]
        TRAIN[train_local.py<br/>Unsloth + LoRA]
        DPO[train_dpo.py<br/>SimPO alignment]
        BATCH[batch_full_pipeline.sh<br/>End-to-end]

        DISTILL --> TRAIN --> DPO
    end

    subgraph Agents_FT["Fine-Tune Agents"]
        STUDENT[Student Agent<br/>Learns from data]
        TEACHER[Teacher Agent<br/>Generates distillation]
        REINFORCER[Reinforcer Agent<br/>DPO/SimPO]
        ANALYST[Analyst Agent<br/>Benchmarks]
        VALIDATOR[Validator Agent<br/>Quality gates]
        DOCUMENTALIST[Documentalist Agent<br/>Docs & reports]
        ARCHIVIST[Archivist Agent<br/>HF upload]
    end

    subgraph Deploy["Phase 3 — Deployment"]
        PROMOTE[promote_model.py<br/>Quality gate]
        GGUF[GGUF Conversion<br/>F16 → Q4_K_M]
        OLLAMA_D[Ollama Deploy<br/>Modelfile + push]
        P2P_D[P2P Distribution<br/>distribute_task]

        PROMOTE --> GGUF --> OLLAMA_D --> P2P_D
    end

    HF_DS --> DISTILL
    DPO --> PROMOTE
    Agents_FT -.->|orchestrate| Training
    Agents_FT -.->|orchestrate| Deploy

    subgraph Stack["Best Stack"]
        MODEL[Qwen2.5-Coder-1.5B]
        UNSLOTH[Unsloth LoRA]
        SIMPO[SimPO Alignment]
        DATASET[Magicoder-OSS-Instruct-75K]
    end
```

## 7. Apple Intelligence Integration Plan

```mermaid
graph TB
    subgraph Current["Current State"]
        COREML_PROV[apple_coreml.py<br/>CoreML Provider<br/>Existing]
        OLLAMA_PROV[ollama.py<br/>Ollama Provider<br/>Existing]
        LLAMA_PROV[llama_cpp.py<br/>llama.cpp Provider<br/>Existing]
    end

    subgraph Phase1["Phase 1 — MLX-LM Runtime"]
        MLX_SERVER[MLX-LM Server<br/>OpenAI-compatible<br/>localhost:8080]
        MLX_PROV[mlx_lm.py<br/>New Provider]
        MLX_QUANT[MLX Quantization<br/>4-bit / 8-bit]

        MLX_SERVER --> MLX_PROV
        MLX_QUANT --> MLX_SERVER
    end

    subgraph Phase2["Phase 2 — Exo Distributed"]
        EXO_CLUSTER[Exo Cluster<br/>Mac-to-Mac inference]
        EXO_PROV[exo.py<br/>New Provider]
        EXO_SHARD[Model Sharding<br/>Cross-device split]
        EXO_DISCO[Device Discovery<br/>Bonjour / mDNS]

        EXO_DISCO --> EXO_CLUSTER
        EXO_SHARD --> EXO_CLUSTER
        EXO_CLUSTER --> EXO_PROV
    end

    subgraph Phase3["Phase 3 — Foundation Models"]
        AFM[Apple Foundation Models<br/>3B on-device]
        SWIFT_BRIDGE[Swift Bridge<br/>Python ↔ Swift IPC]
        AFM_PROV[apple_fm.py<br/>New Provider]

        AFM --> SWIFT_BRIDGE --> AFM_PROV
    end

    subgraph Phase4["Phase 4 — Core AI + Siri"]
        CORE_AI[Core AI Framework<br/>WWDC 2026]
        APP_INTENTS[App Intents<br/>Siri Integration]
        SIRI_BRIDGE[Siri → Mascarade<br/>Voice Commands]

        CORE_AI --> APP_INTENTS --> SIRI_BRIDGE
    end

    subgraph Router_Int["Router Integration"]
        ROUTER_R[Router Strategy<br/>Updated]
        DEVICE_DET[Device Detection<br/>Apple Silicon check]
        AUTO_REG[Auto-Registration<br/>Local models]
    end

    Current --> Phase1
    Phase1 --> Phase2
    Phase2 --> Phase3
    Phase3 --> Phase4

    MLX_PROV --> Router_Int
    EXO_PROV --> Router_Int
    AFM_PROV --> Router_Int
    SIRI_BRIDGE --> Router_Int
```

## 8. Deployment Architecture — Docker Services

```mermaid
graph TB
    subgraph Core_Services["Core Services"]
        CORE_SVC["mascarade-core<br/>FastAPI :8100<br/>2 CPU / 4GB"]
        API_SVC["mascarade-api<br/>Hono :3100<br/>2 CPU / 4GB"]
    end

    subgraph Data_Stores["Data Stores"]
        REDIS_SVC["Redis<br/>Cache + Sessions"]
        PG_SVC["PostgreSQL<br/>Primary DB"]
        QDRANT_SVC["Qdrant<br/>Vector Search"]
        CH_SVC["ClickHouse<br/>Analytics"]
        NEO4J_SVC["Neo4j :7687<br/>Graph DB"]
    end

    subgraph AI_Services["AI / ML Services"]
        OLLAMA_SVC["Ollama<br/>Local LLM Runtime"]
        TTS_SVC["TTS Service"]
        STT_SVC["STT Service"]
        AUDIO_SVC["Generate Audio"]
    end

    subgraph Orchestration["Orchestration"]
        LITELLM_SVC["LiteLLM :4000<br/>LLM Proxy"]
        N8N_SVC["n8n :5678<br/>Workflow Automation"]
        DIFY_API["Dify API"]
        DIFY_WEB["Dify Web"]
        DIFY_WORKER["Dify Worker"]
        GRAPHITI_SVC["Graphiti MCP<br/>:3500"]
    end

    subgraph Agent_Factory["Agent Factory"]
        AF_COCKPIT["Agent Factory Cockpit"]
        AF_DCS["Agent Factory DCS Sandbox"]
    end

    subgraph Observability["Observability Stack"]
        PROM_SVC["Prometheus<br/>Metrics"]
        GRAF_SVC["Grafana<br/>Dashboards"]
        LOKI_SVC["Loki<br/>Log Aggregation"]
        TEMPO_SVC["Tempo<br/>Distributed Tracing"]
        OTEL_SVC["OTEL Collector<br/>Telemetry Pipeline"]
        PROMTAIL_SVC["Promtail<br/>Log Shipper"]
        BB_SVC["Blackbox Exporter<br/>Probes"]
        LANGFUSE_W["Langfuse Worker"]
        LANGFUSE_WEB["Langfuse Web"]
        MINIO_SVC["MinIO<br/>Object Storage"]
    end

    subgraph Edge["Edge"]
        EDGE_PROXY["Edge Proxy<br/>TLS Termination"]
        OPS_AGENT["Ops Agent"]
        FIRECRAWL["Firecrawl<br/>Web Scraping"]
        MEM0_SVC["Mem0<br/>Memory Layer"]
    end

    API_SVC -->|proxy| CORE_SVC
    CORE_SVC --> REDIS_SVC
    CORE_SVC --> PG_SVC
    CORE_SVC --> QDRANT_SVC
    CORE_SVC --> OLLAMA_SVC
    CORE_SVC --> NEO4J_SVC
    GRAPHITI_SVC --> NEO4J_SVC
    CORE_SVC --> OTEL_SVC
    OTEL_SVC --> PROM_SVC
    OTEL_SVC --> LOKI_SVC
    OTEL_SVC --> TEMPO_SVC
    PROM_SVC --> GRAF_SVC
    LOKI_SVC --> GRAF_SVC
    TEMPO_SVC --> GRAF_SVC
    PROMTAIL_SVC --> LOKI_SVC
    EDGE_PROXY --> API_SVC

    LANGFUSE_W --> PG_SVC
    LANGFUSE_W --> CH_SVC
    LANGFUSE_WEB --> PG_SVC
    DIFY_API --> PG_SVC
    DIFY_API --> REDIS_SVC
    N8N_SVC --> PG_SVC
```

## Module Index

| Module | Path | Purpose |
|--------|------|---------|
| Server | `core/mascarade/server.py` | FastAPI application entrypoint |
| Router | `core/mascarade/router/` | LLM provider routing + strategy |
| Providers | `core/mascarade/router/providers/` | 25+ LLM provider adapters |
| Agents | `core/mascarade/agents/` | Specialized agents (KiCad, FreeCAD, SPICE, Components) |
| Orchestrator | `core/mascarade/orchestrator/` | Multi-agent execution engine |
| Plan-and-Execute | `core/mascarade/orchestrator/plan_execute.py` | Plan-and-Execute orchestrator |
| Agentic RAG | `core/mascarade/rag/` | Agentic retrieval-augmented generation |
| Node Engine | `core/mascarade/node_engine/` | Visual graph execution runtime |
| P2P | `core/mascarade/p2p/` | libp2p mesh networking |
| MCP | `core/mascarade/mcp/` | Model Context Protocol client |
| Cache | `core/mascarade/cache/` | Response caching |
| Auth | `core/mascarade/auth.py` | Authentication |
| RBAC | `core/mascarade/rbac.py` | Role-based access control |
| Observability | `core/mascarade/observability/` | OTEL, traces, spans |
| Metrics | `core/mascarade/metrics/` | Prometheus metrics |
| Analytics | `core/mascarade/analytics/` | Usage analytics |
| Finetune | `core/mascarade/finetune/` | Fine-tune orchestration |
| Cluster | `core/mascarade/cluster.py` | Cluster coordination |
| Config | `core/mascarade/config.py` | Central configuration |
| API Routes | `api/src/routes/` | 30 TypeScript route modules |
| Web UI | `web/src/` | React 19 frontend |
| Deploy | `deploy/` | Dockerfiles, observability configs |
| Finetune Pipeline | `finetune/` | Training scripts + datasets |
