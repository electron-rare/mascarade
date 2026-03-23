# LLM Routing & Agent Orchestration — OSS Landscape (2026-03-16)

## Context

Mascarade has two core capabilities that overlap with OSS projects:
1. **LLM Router** — Multi-provider dispatch (10 providers), strategy-based routing (cheapest/fastest/best/specific), circuit breakers, health monitoring, fallback chains
2. **Agent Orchestrator** — Agent registry, multi-agent dispatch, P2P mesh networking

This research evaluates 6 OSS projects across these two categories.

---

## Comparison Table

| Project | Stars | Last Release | Category | License | Language |
|---------|-------|-------------|----------|---------|----------|
| LiteLLM | 38k | Mar 2026 (continuous) | LLM Routing/Proxy | MIT | Python |
| Dify | 100k+ | Mar 2026 (continuous) | Orchestration Platform | Apache 2.0 | Python/TS |
| CrewAI | 46k | Mar 2026 | Agent Orchestration | MIT | Python |
| AutoGen | 50k | Maintenance mode | Agent Orchestration | MIT | Python |
| LangGraph | 26k | Mar 2026 | Agent Orchestration | MIT | Python |
| Semantic Kernel | 27k | Mar 2026 | Agent Orchestration | MIT | C#/Python |

---

## Detailed Evaluations

### 1. LiteLLM (BerriAI) — ⭐ 38k

**What it does:** Unified Python SDK + proxy server (AI Gateway) for 100+ LLM APIs. OpenAI-compatible format, cost tracking, guardrails, load balancing, logging.

**Key features:**
- Unified API across OpenAI, Anthropic, Azure, Bedrock, Vertex, Cohere, HuggingFace, vLLM, etc.
- Proxy server with auth, multi-tenant cost tracking, virtual keys
- Router with retry/fallback logic, load balancing
- Spend tracking per project/user
- Guardrails and caching

**Comparison to Mascarade Router:**
- LiteLLM is a **direct competitor** to Mascarade's router layer
- LiteLLM supports ~100 providers vs Mascarade's 10 — but Mascarade's 10 cover all practical needs
- LiteLLM lacks Mascarade's strategy-based routing (cheapest/fastest/best) — it does simpler load balancing
- Mascarade has domain detection, circuit breakers, and health monitoring built in
- LiteLLM's proxy mode adds overhead Mascarade avoids by being in-process

**Adoption viability:** ⚠️ **Partial — use as reference, not replacement**
- Could replace individual provider implementations (reduce maintenance of 10 provider classes)
- Using LiteLLM as a library (not proxy) for provider abstraction saves maintenance
- But Mascarade's routing strategies and domain detection are unique value — don't cede those
- **Recommendation:** Consider using `litellm.completion()` as the provider backend while keeping Mascarade's router/strategy layer intact

---

### 2. Dify (LangGenius) — ⭐ 100k+

**What it does:** Full-stack LLM application platform with visual workflow builder, RAG, agent capabilities, model management, observability.

**Key features:**
- Drag-and-drop workflow builder
- Built-in RAG pipeline
- Multi-model support with visual prompt engineering
- Agent capabilities with tool integration
- API-first with embeddable UI components
- Observability and monitoring dashboard

**Comparison to Mascarade:**
- Dify is a **platform** while Mascarade is a **system** — fundamentally different design philosophies
- Dify targets teams building LLM apps; Mascarade is a personal agentic system
- Dify's visual builder is irrelevant — Mascarade is code-first
- Dify's RAG and observability features overlap but are tightly coupled to its platform

**Adoption viability:** ❌ **Not viable — architectural mismatch**
- Too opinionated, too heavy, wrong target audience
- Would require rewriting Mascarade to fit Dify's paradigm
- No useful extractable components
- **Recommendation:** Skip. Mascarade's code-first, personal-system approach is the right one.

---

### 3. CrewAI — ⭐ 46k

**What it does:** Role-based multi-agent orchestration framework. Agents have roles, goals, backstories, and collaborate on tasks.

**Key features:**
- Role-based agent definition (role, goal, backstory)
- Sequential and hierarchical task execution
- Built-in tool integration (search, code, file I/O)
- Memory (short-term, long-term, entity)
- First-class MCP support
- Process types: sequential, hierarchical, consensus

**Comparison to Mascarade:**
- CrewAI's agent model is more structured (role/goal/backstory) vs Mascarade's registry-based agents
- CrewAI focuses on multi-agent collaboration; Mascarade's agents are more independent workers
- CrewAI's process types (sequential/hierarchical) could inform Mascarade's orchestration patterns
- Mascarade's P2P mesh networking has no equivalent in CrewAI

**Adoption viability:** ⚠️ **Partial — pattern inspiration**
- CrewAI's role-based mental model is worth adopting for agent definition
- Memory abstractions (short/long-term) could enhance Mascarade's agent memory
- Too opinionated to use as a library within Mascarade
- **Recommendation:** Borrow the role/goal/backstory pattern for agent definitions. Study memory implementation.

---

### 4. AutoGen (Microsoft) — ⭐ 50k

**What it does:** Multi-agent conversation framework. Pioneered the multi-agent paradigm. Now in maintenance mode — superseded by Microsoft Agent Framework.

**Key features:**
- Conversational agent orchestration
- Human-in-the-loop patterns
- Code execution sandboxes
- Group chat orchestration
- Extensive research backing

**Comparison to Mascarade:**
- AutoGen's conversation-based orchestration differs from Mascarade's task-based approach
- AutoGen's group chat pattern is interesting but heavy for personal use
- Now in maintenance mode — no new features, only bug fixes

**Adoption viability:** ❌ **Not viable — maintenance mode**
- Microsoft is merging AutoGen + Semantic Kernel into "Microsoft Agent Framework" (GA Q1 2026)
- No new features coming to AutoGen standalone
- The successor framework is C#-first, poor fit for Python-native Mascarade
- **Recommendation:** Skip. Monitor Microsoft Agent Framework but don't adopt.

---

### 5. LangGraph (LangChain) — ⭐ 26k

**What it does:** Graph-based agent orchestration. Agents and workflows defined as directed graphs with nodes and edges. Stateful, supports cycles and branching.

**Key features:**
- Graph-based workflow definition (nodes + edges)
- Built-in state management and persistence
- Support for cycles (loops, retries)
- Human-in-the-loop at any node
- Streaming support
- LangGraph Platform for deployment

**Comparison to Mascarade:**
- LangGraph's graph model is more explicit than Mascarade's imperative orchestration
- State management and persistence are more mature in LangGraph
- LangGraph is tightly coupled to LangChain ecosystem — heavy dependency chain
- Mascarade's P2P mesh and domain detection have no LangGraph equivalent

**Adoption viability:** ⚠️ **Partial — concepts only**
- Graph-based workflow definition is a strong pattern worth studying
- State checkpointing/persistence could improve Mascarade's agent reliability
- Too coupled to LangChain to use as a library
- **Recommendation:** Adopt graph-based workflow patterns for complex multi-step orchestrations. Study state checkpointing for agent resilience.

---

### 6. Semantic Kernel (Microsoft) — ⭐ 27k

**What it does:** SDK for integrating LLMs into conventional applications. Plugin-based architecture, planner for auto-orchestration, memory connectors.

**Key features:**
- Plugin architecture (native + prompt-based)
- Automatic function calling / planning
- Memory connectors (vector DBs, etc.)
- Multi-language (C#, Python, Java)
- Enterprise-grade, Azure-integrated
- Being merged into Microsoft Agent Framework

**Comparison to Mascarade:**
- Semantic Kernel's plugin model maps loosely to Mascarade's agent registry
- SK's planner (auto-selecting plugins) is similar to Mascarade's router strategy selection
- SK is enterprise/Azure-focused — overkill for personal system
- Python SDK is secondary to C# — less mature

**Adoption viability:** ❌ **Not viable — wrong ecosystem**
- C#-first, Azure-centric — wrong fit for Python-native personal system
- Being merged into Microsoft Agent Framework — uncertain future as standalone
- Plugin architecture is interesting but Mascarade already has equivalent patterns
- **Recommendation:** Skip. No actionable components for Mascarade.

---

## Summary Recommendations

### By Category

**LLM Routing:**
| Action | Project | What to Do |
|--------|---------|------------|
| **Consider** | LiteLLM | Use as provider backend library to reduce maintenance of 10 provider classes. Keep Mascarade's strategy router. |

**Agent Orchestration:**
| Action | Project | What to Do |
|--------|---------|------------|
| **Study** | CrewAI | Adopt role/goal/backstory agent pattern. Study memory abstractions. |
| **Study** | LangGraph | Adopt graph-based workflow patterns. Study state checkpointing. |
| **Skip** | Dify | Architectural mismatch — platform vs system. |
| **Skip** | AutoGen | Maintenance mode, C#-focused successor. |
| **Skip** | Semantic Kernel | Wrong ecosystem (C#/Azure). |

### Key Takeaways

1. **Mascarade's router is differentiated** — strategy-based routing (cheapest/fastest/best), domain detection, and circuit breakers are unique. No OSS project combines all three.
2. **LiteLLM can reduce provider maintenance** — using it as a library (not proxy) could replace 10 individual provider implementations with one unified backend.
3. **Agent patterns are maturing** — CrewAI's role-based model and LangGraph's graph workflows represent best practices worth adopting.
4. **The Microsoft ecosystem is consolidating** — AutoGen and Semantic Kernel are merging. Wait for GA before evaluating.
5. **Mascarade's P2P mesh is unique** — no evaluated framework offers distributed agent communication. This is a competitive advantage.
