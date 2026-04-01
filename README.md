# Mascarade

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Version v0.3.0](https://img.shields.io/badge/version-v0.3.0-orange.svg)
![1100+ commits](https://img.shields.io/badge/commits-1100%2B-informational.svg)

> *"The machine is us, our processes, an aspect of our embodiment."* — Donna Haraway

**Multi-machine agentic LLM orchestration platform.** Mascarade routes prompts across 8+ providers (Claude, Mistral, OpenAI, Ollama, llama.cpp, MLX, Bedrock, and more), runs a decentralized P2P mesh across 5 physical nodes, fine-tunes domain-specific mini-models that beat HuggingFace baselines by +162%, and exposes MCP tools for hardware engineering workflows. Not a framework — a distributed organism running in production.

[Documentation](docs/index.md)

---

## Architecture

```mermaid
graph TD
    Client["Clients (curl, SDK, MCP, Xcode)"] --> API["API Gateway\nHono :3100\nAuth, Rate Limit, OpenAI compat"]
    API --> Core["Core Engine\nFastAPI :8100\nRouter, Agents, Orchestrator"]
    Core --> Providers["8+ LLM Providers\nClaude, Mistral, OpenAI, Google\nOllama, llama.cpp, MLX, Bedrock"]
    Core <--> P2P["P2P Mesh :4001\nEd25519 auth, DHT, PubSub"]
    P2P --- N1["GrosMac\nApple M5"]
    P2P --- N2["Tower\nCPU inference"]
    P2P --- N3["KXKM-AI\nRTX 4090"]
    P2P --- N4["VM\nDocker host"]
    P2P --- N5["CILS\nOllama inference"]
    Core <--> RAG["RAG Pipeline\nbge-m3 + Qdrant + SearXNG"]
    Core <--> MCP["MCP Server + Client\nKiCad, SPICE, FreeCAD"]
```

---

## Key Features

**Routing**
- 8+ LLM providers with strategy-based selection (BEST / CHEAPEST / FASTEST)
- Fallback chains, ML router (softmax classifier, 17 features), Ollama multi-machine routing

**P2P Mesh**
- Ed25519 authentication, DHT discovery, PubSub messaging
- Capability-based task routing, NAT relay traversal, 5 active nodes

**Agents**
- 10+ builtin agents, domain agents (KiCad, SPICE, FreeCAD, component search)
- Plan-and-execute orchestrator with task decomposition and dependency management

**Fine-tuning**
- Teacher-to-student distillation pipeline: CPT, SFT, RLVR
- Unsloth + SimPO + LoRA/QLoRA, 29 domain-specific models on [HuggingFace](https://huggingface.co/clemsail)
- +162% vs HuggingFace #1 electronics model on 130-prompt benchmark

**RAG**
- bge-m3 embeddings, Qdrant hybrid search (dense + BM25 + RRF)
- LLM reranking, CRAG fallback, SearXNG web search

**MCP**
- Server: 5 tools exposed via Model Context Protocol
- Client: KiCad (5 tools), SPICE (28 tools), FreeCAD, n8n, ERPNext

**Observability**
- Langfuse (LLM traces), Prometheus + Grafana (metrics), OpenTelemetry (distributed tracing)

**API Compatibility**
- OpenAI `/v1/chat/completions`, Ollama `/api/chat`, Xcode Intelligence
- Drop-in replacement for Continue.dev, Open WebUI, LM Studio

---

## Quickstart

```bash
git clone https://github.com/electron-rare/mascarade.git
cd mascarade
cp .env.example .env          # add your API keys
docker compose --profile core up -d
curl http://localhost:3100/v1/models
```

---

## Fine-tuned Models

29 domain-specific models published on [HuggingFace (clemsail)](https://huggingface.co/clemsail), trained on 498K+ curated examples across electronics engineering domains.

| Model | Domain | Examples | Base |
|-------|--------|----------|------|
| mascarade-spice-v3 | SPICE simulation | 13,723 | Qwen2.5-3B |
| mascarade-verilog-v1 | Verilog / RTL | 26,532 | Qwen2.5-3B |
| mascarade-emc-v2 | EMC/EMI compliance | 3,016 | Qwen2.5-3B |
| mascarade-kicad-v4 | KiCad 10 PCB design | 1,931 | Qwen2.5-3B |
| mascarade-embedded-v3 | Embedded systems | 1,669 | Qwen2.5-3B |
| mascarade-dsp-v2 | DSP (ARM CMSIS) | 2,015 | Qwen2.5-3B |

Data quality pipeline: SemDeDup, IFD scoring, multi-judge (3 LLMs), capability scoring. [Full list on HuggingFace.](https://huggingface.co/clemsail)

---

## Benchmarks

Evaluated by Codestral judge on 130 prompts (100 standard + 30 adversarial), electronics engineering domain:

| Model | Size | Score /10 | vs phi2-EE (HF #1) |
|-------|------|-----------|---------------------|
| **mascarade-emc** | 2.5 GB | **7.14** | **+162%** |
| **mascarade-power** | 2.5 GB | **7.10** | +161% |
| **mascarade-dsp** | 2.5 GB | **7.07** | +160% |
| **mascarade-spice-v1** | 2.5 GB | **6.89** | +153% |
| qwen2.5-7b (base) | 4.7 GB | 6.89 | +153% |
| phi2-ee (HF #1 EE) | 1.7 GB | 2.72 | baseline |

Mascarade fine-tunes outperform the top HuggingFace electronics model by +162% while being smaller than the base model.

---

## Related Projects

| Repository | Description |
|------------|-------------|
| [Kill_LIFE](https://github.com/electron-rare/Kill_LIFE) | Spec-first agentic methodology for embedded systems (ESP32, STM32) |
| [crazy_life](https://github.com/electron-rare/crazy_life) | React cockpit and workflow editor for Mascarade |
| [prima-cpp](https://github.com/electron-rare/prima-cpp) | Distributed multi-node LLM inference (ring topology, NAT relay) |
| [KiC-AI](https://github.com/electron-rare/KiC-AI) | AI-powered PCB design assistant for KiCad |

---

## License

[MIT](LICENSE.md) — Copyright (c) 2026 [L'Electron Rare](https://github.com/L-electron-Rare)

---

*"The cyborg does not dream of community on the model of the organic family. It is not made of mud and cannot dream of returning to dust."*
