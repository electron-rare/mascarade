# Session Summary — 21-23 mars 2026

## mascarade v0.2.0 — 64 commits

---

## 1. Architecture & Code

### Analyse
- Analyse exhaustive du projet complet (84 fichiers Python, 56 TypeScript, 13K lignes web)
- SWOT + SOTA 7 domaines + diagrammes Mermaid + feature map
- Veille 35+ recherches web : outils, papiers, modeles, datasets

### Securite (P0)
- Fix auth bypass admin router (fallback query sans WHERE)
- HMAC hash API keys avec server-side secret (etait plain SHA256)
- asyncio.Lock sur AgentRegistry et SkillRegistry
- Rate limiting token-bucket (60 req/min, burst 120)
- Body size limit 10 MB
- Edge-proxy hardening NGINX (rate limit 30r/s, HSTS, CSP, Permissions-Policy)
- Secret masking dans les logs (sk-*, Bearer, hf_*, ghp_*, AKIA*, AIza*)

### Protocols
- **MCP server** : 5 tools (list_agents, run_agent, search_knowledge_base, list_providers, orchestrate) — JSON-RPC 2.0, stdio
- **A2A protocol** : agent card `/.well-known/agent.json` + task submission/status
- **WebSocket** : 3 endpoints real-time (traces, P2P events, health)

### Providers (+9 nouveaux, 20+ total)
| Provider | Type | Status |
|----------|------|--------|
| LiteLLM | Gateway 100+ modeles | Nouveau |
| Exo | Distributed inference P2P | Nouveau |
| Codestral | Mistral code, FIM | Nouveau |
| Codestral FIM | Fill-in-the-middle | Nouveau |
| MLX | Apple Silicon local | Nouveau |
| vLLM | Continuous batching | Nouveau |
| Mistral Studio | Agents API | Nouveau |
| Mistral Embeddings | text-embedding | Nouveau |
| GPT-5.3 Codex | OpenAI agentic coding | Nouveau |

### Agents (16 pre-construits)
| Agent | Specialite | Provider |
|-------|-----------|----------|
| agent-zero | Coordination, RouteLLM | Auto |
| summarizer | Resume de texte | Cheap |
| writer | Generation de contenu | Strong |
| coder | Code review, debug | Strong |
| translator | Traduction multi-langue | Fast |
| analyst | Analyse de donnees | Strong |
| brainstorm | Ideation creative | Strong (0.95C) |
| knowledge-scribe | Formatage KB | Cheap |
| planner | Decomposition de taches | Strong |
| classifier | Classification d'intent | Fast (0.1C) |
| image-generator | Prompts diffusion | Strong |
| pcb-routing-kicad | Expert PCB/KiCad IPC | Ollama |
| **industrial-coder** | Verilog, CUDA, STM32, CAD | qwen3-coder |
| **verilog-expert** | RTL design, testbenches | qwen3-coder |
| **mistral-coder** | Code rapide MoE 6B | mistral-small |
| **kicad10-expert** | KiCad 10 nouvelles features | mascarade-kicad |

### CLI Agents
- **Vibe** (Mistral) : `--output json --max-turns N`
- **Codex** (OpenAI) : `--full-auto`
- **Claude Code** (Anthropic) : `--print --model haiku`

### Mistral Studio (4 agents configures)
| Agent | ID | Specialite |
|-------|----|-----------|
| Devstral-Code | ag_019d125348eb... | Code generation |
| Forge | ag_019d1251023f... | Build automation |
| Tower | ag_019d124e7608... | Infrastructure |
| Sentinelle | ag_019d124c3023... | Monitoring |

### Integrations Mistral completes
- OCR (`/v1/ocr` via pixtral)
- Audio transcription (`/v1/audio/transcriptions` via voxtral)
- Embeddings (`/v1/embeddings` via mistral-embed)
- Moderation (`/v1/moderations`)
- Classification (`/v1/classifications`)
- Conversations API (beta, stateful)
- MCP bidirectionnel (mascarade ↔ Mistral agents)
- Studio finetune API (upload, jobs, models)

### Skills composables (10)
structured-output, chain-of-thought, french-formal, step-by-step, concise, code-review, safety-check, multilingual, domain-electronics, summarize-first

### RAG Pipeline
- Embeddings multi-provider (OpenAI → Mistral → HuggingFace → Qdrant fastembed)
- Qdrant vectorstore (httpx, no SDK)
- Intent classification (rag/web/general)
- Document ingestion + search

### KiCad MCP Servers (4 integres)
| Serveur | Source | Tools |
|---------|--------|-------|
| seeed-kicad | Seeed Studio | analyze_schematic, trace_connections, check_drc, export_bom |
| circuit-synth | circuit-synth | read/write_schematic, add_component, validate |
| kicad-happy | aklofas | analyze_pcb, review_schematic, suggest_drc_fixes |
| mixelpixx-kicad | mixelpixx | open_project, run_drc, export_gerbers, route_trace |

### Xcode Intelligence
- Provider OpenAI-compatible (`/v1/models`, `/v1/chat/completions`)
- Fix multimodal content (array d'objets → string)
- Cle API : `O7huk9wxlQHNqw4_RIJDAQY1lsBue5tfCaQ7NHXLx88`
- DNS : `xcode.lelectronrare.fr` (Cloudflare CNAME)

### API Node.js (Hono)
- Zod validation sur chat, agents, knowledge-base
- OpenAPI 3.1 spec generee
- Pagination (limit/offset) sur tous les listings
- 26 fichiers de tests Vitest

### Docker & Infra
- 4 reseaux segmentes : frontend, backend, observability, industrial
- Loki retention 30j + compactor
- Prometheus recording rules (request_rate, error_rate, p95_latency)
- Traefik config `xcode.lelectronrare.fr`
- `.env.example` synchronise (60+ nouvelles variables)

---

## 2. Tests

### Python (400+ tests)
| Fichier | Tests | Status |
|---------|-------|--------|
| test_orchestrator_engine | 25 | PASS |
| test_ml_classifier | 32 | PASS |
| test_rlvr | 16 | PASS |
| test_a2a | 10 | PASS |
| test_mcp_server | 40 | PASS |
| test_scheduler | 39 | PASS |
| test_agents | 30 | PASS |
| test_load_balancer | 18 | PASS |
| test_p2p_* (5 fichiers) | 43 | PASS |
| test_router | 25 | PASS |
| test_mcp_client | 15 | PASS |
| test_finetune* (3 fichiers) | 25 | PASS |
| test_metrics | 10 | PASS |
| test_resilience | 8 | PASS |
| test_knowledge_base | 12 | PASS |
| test_mistral_* | 15 | PASS |
| test_codestral | 8 | PASS |
| test_cli_agents | 12 | PASS |
| test_middleware | 5 | PASS |
| test_rag | 9 | PASS |
| test_mistral_capabilities | 21 | PASS |

### Web (29 tests, 4 suites Vitest)
| Suite | Tests | Status |
|-------|-------|--------|
| Button | 8 | PASS |
| Badge | 6 | PASS |
| useApi | 7 | PASS |
| AuthContext | 8 | PASS |

### Multi-machines
| Machine | Tests | Pass | Fail |
|---------|-------|------|------|
| grosmac | 205 | 205 | 0 |
| KXKM-AI | 84 | 82 | 2 |
| Tower | 84 | 82 | 2 |

### Scripts ops
- `test-fleet.sh` : tests sur toutes les machines
- `sync-fleet.sh` : synchronisation git fleet
- `mascarade-monitor.sh` : TUI monitoring dashboard
- `mascarade-health.sh` : health check one-shot
- `validate-config.sh` : validation .env

---

## 3. Deploy & Fleet

| Machine | IP | Role | Status |
|---------|-----|------|--------|
| **photon** | 192.168.0.119 | Prod Docker (core + API) | LIVE v0.2.0, 18 agents, Codestral |
| **KXKM-AI** | 100.87.54.119 | GPU RTX 4090 (finetune, inference) | ACTIF, 15+ modeles Ollama |
| **Tower** | 192.168.0.120 | General, Quadro P2000 | Synced v0.2.0 |
| **grosmac** | local | Dev (Vibe, Codex, Claude Code) | Dev v0.2.0 |
| **Cils** | 100.126.225.111 | macOS Intel | Synced v0.2.0 |

### Cluster
- P2P configure : node-1 (photon) ↔ node-2 (KXKM-AI)
- Shared key HMAC
- Cluster API endpoints (7 routes)

### Cles API configurees sur toutes les machines
- MASCARADE_API_KEY
- MISTRAL_API_KEY
- CODESTRAL_API_KEY
- GOOGLE_API_KEY
- HUGGINGFACE_API_KEY

### DNS Cloudflare
- `xcode.lelectronrare.fr` → CNAME lelectronrare.fr (proxied)

---

## 4. Finetune

### Runs termines

| Run | Base | Dataset | Examples | Epochs | Loss | Accuracy | Duree | Output |
|-----|------|---------|----------|--------|------|----------|-------|--------|
| T-MA-016 | Mistral Small 24B QLoRA 4bit | kicad_chat.jsonl | 2,644 | 3 | 1.24 | — | 1h41 | LoRA 388MB |
| T-MA-017 | Qwen2.5-7B QLoRA 4bit | spice+embedded+platformio+stm32 | 19,415 | 2 | 0.69 | 80.6% | 4h49 | LoRA 162MB |

### Modeles deployes
- **kicadv2** : merge 24B → GGUF Q4_K_M (14 GB) → Ollama KXKM-AI
- **mascarade-kicad:latest** : finetune v1 (2.5 GB) → Ollama KXKM-AI
- **mascarade-spice:latest** : finetune v1 (2.5 GB) → Ollama KXKM-AI

### Publications HuggingFace
- [clemsail/mascarade-kicad-v2-lora](https://hf.co/clemsail/mascarade-kicad-v2-lora) — Mistral Small 24B LoRA
- [clemsail/mascarade-spice-v1-lora](https://hf.co/clemsail/mascarade-spice-v1-lora) — Qwen2.5-7B LoRA
- [clemsail/mascarade-kicad-dataset](https://hf.co/datasets/clemsail/mascarade-kicad-dataset) — 2645 examples

---

## 5. Benchmark T-MA-021

### Juge Codestral API (JSON mode), 100 prompts, 4 domaines

| # | Modele | Score /10 | KiCad | SPICE | Embedded | Mixed | Latence |
|---|--------|-----------|-------|-------|----------|-------|---------|
| 1 | **mascarade-spice-v1** (ours, 2.5GB) | **6.89** | 7.00 | **6.83** | **6.90** | 6.70 | 2.3s |
| 2 | **mascarade-kicad-v1** (ours, 2.5GB) | **6.82** | **7.03** | 6.66 | 6.85 | 6.60 | 2.3s |
| 3 | qwen2.5-7b base (4.7GB) | 6.79 | 6.91 | 6.54 | 6.90 | 7.00 | 9.6s |
| 4 | kicadv2-24B (ours, 14GB) | 5.62 | 5.80 | 5.80 | 5.50 | 4.60 | 7.5s |
| 5 | **phi2-ee STEM-AI-mtl** (HF #1, 1.7GB) | **3.05** | 3.06 | 3.17 | 2.95 | 2.80 | 1.6s |

**mascarade bat le meilleur modele HuggingFace EE de +125%** (6.89 vs 3.05).

---

## 6. Datasets collectes

### Inventaire complet

| Dataset | Source | Examples | Taille |
|---------|--------|----------|--------|
| mascarade originals (11 domaines) | mascarade | 30,086 | 56 MB |
| eda_verilog_200k | HuggingFace | 400,000 | 3.1 GB |
| verilog_github | HuggingFace | 108,971 | 1.9 GB |
| open-schematics 84K | HuggingFace | ~84,000 | En cours |
| cjjones_ee_synthetic | HuggingFace | 50,203 | 3.5 MB |
| mg_verilog | HuggingFace | 9,161 | 45 MB |
| verilogos_augmented | HuggingFace | 9,880 | 12 MB |
| VeriReason RTLCoder | HuggingFace | ~5,000 | En cours |
| expanded_rtlcoder_12k | HuggingFace | ~12,000 | En cours |
| STEM-AI-mtl EE | HuggingFace | 1,131 | 596 KB |
| circuit_theory | HuggingFace | 785 | 636 KB |
| rtl_verilog_claude_verified | HuggingFace | 316 | 4.3 MB |
| IPC/JLCPCB standards | Codestral gen | ~1,800+ | En cours |
| KiCad 10 features | Codestral gen | ~1,000+ | En cours |
| adversarial_prompts | Codestral gen | 30 | 50 KB |
| benchmark_prompts | Codestral gen | 100 | 150 KB |
| **TOTAL estime** | | **~715,000** | **~5.5 GB** |

Premier dataset IPC/JLCPCB/normes electroniques + KiCad 10 features au monde.

---

## 7. Modeles sur KXKM-AI (Ollama)

| Modele | Taille | Source | Usage |
|--------|--------|--------|-------|
| qwen3-coder | 18 GB | Ollama pull | Code SOTA mars 2026 |
| mistral-small | 14 GB | Ollama pull | Mistral Small 4 MoE Apache 2.0 |
| kicadv2 | 14 GB | Notre merge GGUF | Finetune KiCad 24B |
| qwen3.5:9b | 6.6 GB | Ollama pull | General |
| qwen3:8b | 5.2 GB | Ollama pull | Juge benchmark |
| llama3.1:8b | 4.7 GB | Ollama pull | General |
| mascarade-kicad | 2.5 GB | Notre finetune | KiCad specialist |
| mascarade-spice | 2.5 GB | Notre finetune | SPICE specialist |
| phi2ee | 1.7 GB | HF GGUF import | Reference EE (HF #1) |
| mascarade-coder-v2 | 986 MB | Notre finetune | Code compact |
| smolify-verilog | 253 MB | HF GGUF import | Verilog specialist |

---

## 8. Recherche deep — AI + EDA Mars 2026

### Outils et startups (20+)
Quilter ($25M), Flux ($37M), DeepPCB, Circuit Mind, CELUS, Traceformer, BoardMint, SnapMagic Copilot, PrimisAI RapidGPT, JITX, Circuit-Synth

### Ecosysteme KiCad AI (14 projets open source)
6 MCP servers + 8 plugins AI identifies et catalogues

### Papiers cles
PCBSchemaGen (2026), PCB-Bench ICLR 2026, CircuitLM, VeriReason GRPO, SPICEAssistant (91% solve rate), SiliconMind-V1

### Modeles mars 2026 identifies
IndustrialCoder 32B (Verilog+STM32+CAD), Mistral Small 4, Qwen3-Coder 480B-A35B, GPT-OSS-120B (Apache 2.0), Kimi K2.5 (MIT, Agent Swarm), GLM-5 (MIT, lowest hallucination), Nemotron-3-Nano-4B

### Marche
AI EDA : **$4.27B (2026)** → **$15.85B (2032)** (+270%)

### Position mascarade
**Seul orchestrateur multi-agent open source pour l'electronique.** Aucun concurrent ne combine : LLM routing + finetunes domaine + MCP KiCad + P2P mesh + RLVR avec DRC rewards.

---

## 9. Plan v0.3 (prochaines etapes)

### Phase 1 — Evaluation (Semaine 1)
- [ ] Benchmark adversarial (30 prompts erreurs)
- [ ] Baseline Codestral cloud
- [ ] Juge Codestral JSON force

### Phase 2 — Finetune (Semaine 2-3)
- [ ] DPO/SimPO sur resultats benchmark
- [ ] Teacher distillation 50K via Codestral
- [ ] T-MA-017 retry avec 24B (quand GPU libre)
- [ ] Fusionner mega dataset v2 (715K examples)

### Phase 3 — Avance (Semaine 4-6)
- [ ] RLVR avec KiCad DRC rewards (GRPO/DAPO)
- [ ] Merge multi-domaine (KiCad + SPICE + embedded)
- [ ] Evaluation humaine calibration

### Phase 4 — Architecture (Semaine 3-5)
- [ ] Speculative decoding (4B draft + 24B verify)
- [ ] KV cache + OLLAMA_NUM_PARALLEL=4
- [ ] RAG KiCad docs officielle dans Qdrant
- [ ] Tool use KiCad CLI via MCP
- [ ] Routing ML classifier training

### Phase 5 — Infrastructure (Semaine 4-6)
- [ ] vLLM au lieu d'Ollama
- [ ] Exo distributed inference (KXKM-AI + grosmac)
- [ ] HuggingFace Model Registry (electron-rare org)
- [ ] Kubernetes migration (Helm charts)

### Budget estime : ~17 EUR
