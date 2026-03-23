# AI + Electronics/EDA Landscape -- Deep Research Report
**Date:** 2026-03-23 | **Author:** Claude Opus 4.6 for L'Electron Rare / Mascarade

---

## TABLE OF CONTENTS

1. [PART 1: AI-Powered EDA Tools & Startups](#part-1-ai-powered-eda-tools--startups)
2. [PART 2: Open-Source AI + KiCad Ecosystem](#part-2-open-source-ai--kicad-ecosystem)
3. [PART 3: Academic Research](#part-3-academic-research)
4. [PART 4: Industry Trends](#part-4-industry-trends)
5. [PART 5: Datasets & Benchmarks](#part-5-datasets--benchmarks)
6. [PART 6: Mascarade Integration Opportunities](#part-6-mascarade-integration-opportunities)

---

## PART 1: AI-Powered EDA Tools & Startups

### 1.1 Autonomous PCB Design Platforms

#### Quilter
- **URL:** https://www.quilter.ai/
- **What:** Physics-driven, reinforcement-learning-based autonomous PCB layout engine. Generates multiple full-board candidates in parallel.
- **Features:** Autonomous placement + routing, DRC-clean output, multi-candidate generation, integrates with Altium/Cadence/Siemens Xpedition, private cloud and GovCloud deployment, on-premise available.
- **Pricing:** Free tier for hobbyists/students/companies <10 employees or <$50k revenue. Pay-per-download model scaled by pin count (not per-seat). Unlimited iterations free; pay only for approved designs.
- **Funding:** $25M Series B (October 2025).
- **API:** Not public; integrates via file import/export with major EDA tools.
- **Open source:** No.

#### Flux.ai (Defy Gravity Inc.)
- **URL:** https://www.flux.ai/
- **What:** Browser-based AI-powered PCB design tool. Supports design from prompt to production. Up to 8-layer boards for IoT, wearables, robotics.
- **Features:** AI chat assistant, AI-assisted schematic + layout, collaborative browser editor, prompt-to-PCB workflow, Copilot (industry-first AI hardware design assistant integrated in PCB tool).
- **Pricing:** Free tier (basic schematic editing, limited AI). Starter $20/mo, Pro $142/mo, Teams $158/mo. Usage metered in ACUs (AI Compute Units).
- **Funding:** $37M total ($24M Series B led by 8VC, February 2026).
- **API:** Not documented publicly.
- **Open source:** No.

#### DeepPCB (by InstaDeep/BioNTech)
- **URL:** https://deeppcb.ai/
- **What:** Pure AI-powered, cloud-native PCB routing using reinforcement learning. Built on Google Cloud.
- **Features:** DRC-clean layout generation, via minimization, up to 8 layers, 1200 connections, differential pairs, AI-powered placement (up to 1000 components, 2200 pins), multi-plane support.
- **Pricing:** Free trial + pay-as-you-go AI credits.
- **Accepts:** KiCad DSN files, returns routed SES files.
- **API:** Cloud API (details via contact).
- **Open source:** No.

### 1.2 AI Schematic & BOM Generation

#### Circuit Mind
- **URL:** https://www.circuitmind.io/
- **What:** AI-powered schematic + BOM generation in 60 seconds from architecture block diagram.
- **Features:** Automated component selection (optimized for size/cost/power/availability), multiple design options with trade-off sliders, procurement data integration, export to Altium/OrCAD/Expedition.
- **Pricing:** Enterprise/contact-based.
- **API:** Not public.
- **Open source:** No.

#### CELUS
- **URL:** https://www.celus.io/
- **What:** AI electronics design platform. Requirements-to-schematic in <1 hour.
- **Features:** 17M+ component library, AI design assistant (accepts natural language + whiteboard sketches), automated architecture recommendations, BOM generation with lifecycle/supply/pricing data, ECAD tool integration.
- **Pricing:** Free tier to start. Enterprise plans available.
- **API:** Not public.
- **Open source:** No.

#### Skimatly
- **URL:** https://www.skimatly.xyz/
- **What:** AI schematic generator from natural language. IEEE-standard schematics with KiCad-quality symbols.
- **Pricing:** Unknown.
- **Open source:** Unknown.

### 1.3 Hardware Description Language / Code-Driven Design

#### JITX
- **URL:** https://www.jitx.com/
- **GitHub:** https://github.com/JITx-Inc
- **What:** Software-defined electronics. Describe design constraints in code, JITX generates geometry that meets requirements.
- **Features:** Constraint-driven autorouting, Python front-end (migrated from Stanza DSL, launched Q4 2025), open components database, regenerates when requirements change, AI-assisted code generation.
- **Pricing:** Not publicly listed.
- **Open source:** Open components database (https://github.com/JITx-Inc/open-components-database). Core tool is proprietary.

#### Circuit-Synth
- **URL:** https://www.circuit-synth.com/
- **GitHub:** https://github.com/circuit-synth/circuit-synth
- **PyPI:** https://pypi.org/project/circuit_synth/
- **What:** Python-defined circuits with Claude Code as intelligent design partner. Bi-directional KiCad integration.
- **Features:** Python circuit definitions, AI-generated circuits via Claude Code, JLCPCB real-time pricing/availability, SPICE simulation setup, FMEA analysis, BOM management, 7 pre-made manufacturing-ready patterns, MCP server for KiCad schematic manipulation.
- **Pricing:** Open source (free).
- **Open source:** Yes.

### 1.4 AI Schematic Review & Validation

#### Traceformer
- **URL:** https://traceformer.io/
- **What:** AI schematic checker for KiCad and Altium. Datasheet-backed, application-level validation complementing ERC/DRC.
- **Features:** Cross-references schematics against component datasheets, validates pin functions/voltage levels/IC configurations, cites specific datasheet pages, KiCad plugin (7.0+), three-phase splitter pipeline, cost transparency per review. Does not train on your IP.
- **Pricing:** Pay-per-review with exact cost shown before execution.
- **API:** Via KiCad plugin or web upload.
- **Open source:** No (plugin is free).

#### BoardMint
- **URL:** https://boardmint.io/
- **What:** AI-powered PCB design analysis and validation.
- **Features:** 12 physics engines + AI, 100+ IPC/IEC compliance checks in <30 seconds, DRC/thermal/safety/signal integrity/EMC analysis, supports KiCad/Altium/Eagle/Cadence.
- **Pricing:** Free to start.
- **Open source:** No.

### 1.5 AI BOM & Supply Chain

#### Luminovo
- **URL:** https://luminovo.com/
- **What:** Electronics supply chain platform with AI-powered BOM management.
- **Features:** AI BOM importer (MPN recognition, pattern learning), PCB instant pricing, 1000+ global supplier integrations, lifecycle/compliance/availability dashboard, CPQ (Configure-Price-Quote) for EMS.
- **Pricing:** Enterprise SaaS.
- **Open source:** No.

#### PartGenie
- **URL:** https://www.partgenie.ai/
- **What:** AI-powered component search and BOM tool.
- **Features:** Natural language component search across 22M+ parts, BOM upload with obsolescence/risk warnings, datasheet analysis (upload circuit diagrams/photos/layouts), pin-compatible alternative finder.
- **Pricing:** Free tier + paid plans with 30-day trial. Enterprise with private deployment.
- **Open source:** No.

#### Wizerr AI BOM Optimizer
- **URL:** https://www.wizerr.ai/bom-optimizer
- **What:** AI-powered BOM intelligence and optimization.

#### DigiBull AI
- **URL:** https://digibull.ai/
- **What:** BOM intelligence for electronics quality and reliability.

### 1.6 AI Copilots & Assistants

#### SnapMagic (ex-SnapEDA)
- **URL:** https://www.snapmagic.com/
- **What:** AI copilot for electronics design, used by 1.5M+ engineers.
- **Features:** Circuit auto-completion (e.g., auto-place decoupling caps), natural language PCB design instructions, component recommendations, real-time supply chain data, BOM optimization. Integrates with Autodesk Fusion and Altium.
- **Funding:** Y Combinator backed.
- **Open source:** No.

#### PrimisAI RapidGPT
- **URL:** https://primis.ai/
- **What:** Generative AI for FPGA/ASIC hardware design.
- **Features:** Natural language to Verilog/VHDL, concept-to-bitstream/GDSII, on-premise deployment, extensible knowledge base for client IPs. VS Code extension available.
- **Pricing:** Free tier + Premium (launched February 2026).
- **Open source:** No. HuggingFace presence: https://huggingface.co/PrimisAI

#### GerberGPT
- **URL:** https://gerbergpt.com/
- **What:** AI-powered PCB production optimization from Gerber files.
- **Features:** Component inference, cost reduction, PCB size optimization.

### 1.7 AI Simulation & Signal Integrity

#### Cirkit Designer
- **URL:** https://www.cirkitstudio.com/
- **What:** AI-powered circuit design and simulation.
- **Features:** AI tools for 10x faster circuit design, simulation integration.

#### Keysight ADS AI Assistants
- **URL:** https://www.keysight.com/us/en/lib/resources/miscellaneous/eda-ai.html
- **What:** AI Chat (Learning Assistant) + Copilot (Tool Assistant) for ADS.
- **Features:** Natural language queries for RF/high-speed design, automated EM simulation commands, on-premises deployment (data never leaves org), specialized EDA training data.
- **Pricing:** Included with existing ADS subscriptions at no additional cost (ADS 2026 Update 1).
- **Open source:** No.

---

## PART 2: Open-Source AI + KiCad Ecosystem

### 2.1 KiCad MCP Servers (Model Context Protocol)

| Project | GitHub | Stars | Description |
|---------|--------|-------|-------------|
| **Seeed-Studio kicad-mcp-server** | [Seeed-Studio/kicad-mcp-server](https://github.com/Seeed-Studio/kicad-mcp-server) | -- | MCP server for KiCad 9.0. Hardware design validation + embedded code generation. Backed by Seeed Studio. |
| **mixelpixx KiCAD-MCP-Server** | [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) | -- | 122 tools in 16 categories. MCP 2025-06-18 spec. Targets Cline/VSCode + Claude. JLCPCB integration guide. |
| **lamaalrajih kicad-mcp** | [lamaalrajih/kicad-mcp](https://github.com/lamaalrajih/kicad-mcp) | -- | Cross-platform (Mac/Windows/Linux). DRC, netlist extraction, PCB visualization, circuit pattern recognition. |
| **circuit-synth mcp-kicad-sch-api** | [circuit-synth/mcp-kicad-sch-api](https://github.com/circuit-synth/mcp-kicad-sch-api) | -- | MCP server for KiCad schematic manipulation. Create/modify/analyze .kicad_sch files via AI agents. |
| **Finerestaurant kicad-mcp-python** | [Finerestaurant/kicad-mcp-python](https://github.com/Finerestaurant/kicad-mcp-python) | -- | Uses KiCad's official IPC-API for stable AI integration. |
| **miyosuda kicad-mcp-server** | [miyosuda/kicad-mcp-server](https://github.com/miyosuda/kicad-mcp-server) | -- | Fork/variant enabling Claude direct KiCad interaction. |

### 2.2 KiCad AI Plugins

| Project | GitHub/URL | Description |
|---------|-----------|-------------|
| **ALT TAB KiCad AI Plugin** | [kicad.alttab.rs](https://kicad.alttab.rs/) | AI chatbot inside KiCad. 1,500+ users, 1,600+ downloads. Plans for KiCad Agent (prompt-to-schematic+PCB). |
| **SmartonAI** | [smarton-empower/Smarton-AI](https://github.com/smarton-empower/smarton-ai) | HuggingGPT-inspired plugin. Task planning + execution for PCB/schematic design. Interactive AI tutor. |
| **K-AI** | [colaco1123/K-AI](https://github.com/colaco1123/K-AI) | Describe circuit in text, Claude generates KiCad schematic. No API key required (browser-based). |
| **Smart-Cat** | [BWolf-16/Smart-Cat](https://github.com/BWolf-16/Smart-Cat) | AI assistant for KiCad 7+. Supports Claude and OpenAI APIs for design analysis. |
| **KiC-AI** | [jochemkroon/KiC-AI](https://github.com/jochemkroon/KiC-AI) | AI chat + PCB analysis + real-time component pricing. **Local LLM support via Ollama.** |
| **image2KiCAD** | [Monacrylic/image2KiCAD](https://github.com/Monacrylic/image2KiCAD) | Convert images to KiCad schematics using AI. |
| **kicad-llm-plugin** | [jasiek/kicad-llm-plugin](https://github.com/jasiek/kicad-llm-plugin) | Inspect schematics with any LLM model, get improvement suggestions. |
| **kicad-happy** | [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy) | Claude Code skills for KiCad: schematic analysis, PCB review, datasheet download, component sourcing, fab prep. |

### 2.3 KiCad Automation Libraries

| Project | GitHub | Description |
|---------|--------|-------------|
| **kicad-tools** | [rjwalters/kicad-tools](https://github.com/rjwalters/kicad-tools) | Python tools for LLMs/agents to parse and manipulate KiCad files programmatically. |
| **kicad-netlist-tool** | [MichaelAyles/kicad-netlist-tool](https://github.com/MichaelAyles/kicad-netlist-tool) | Extracts netlists in TOKN format -- token-efficient representation optimized for LLM processing. |
| **KiKit** | [yaqwsx/KiKit](https://github.com/yaqwsx/KiKit) | Automation tools for KiCad (panelization, DRC, fab output). Foundation for AI workflows. |
| **kicad-automation-scripts** | [productize/kicad-automation-scripts](https://github.com/productize/kicad-automation-scripts) | Python + UI automation for KiCad processes. |
| **pcb-designer-ai-agent** | [assalas/pcb-designer-ai-agent](https://github.com/assalas/pcb-designer-ai-agent) | ML-powered component placement, routing optimization, signal integrity. Supports KiCad, Altium, Eagle. |
| **OrthoRoute** | [bbenchoff.github.io/pages/OrthoRoute](https://bbenchoff.github.io/pages/OrthoRoute.html) | GPU-accelerated autorouter for KiCad using PathFinder algorithm. KiCad IPC API plugin. |

### 2.4 KiCad 10 Status (Released 2026-03-20)

KiCad 10.0.0 was officially released on March 20, 2026. Key features:
- Wire crossing hop-over arcs
- Jumper definitions (connected pin sets)
- Design Blocks extended to PCB editor
- Overhauled track tuning system (time-domain constraints, Tuning Profiles)
- More robust Python scripting API

**No native AI features** are included in KiCad 10. The official project has not adopted any AI/ML tooling. All AI integration comes from the community plugin ecosystem described above.

---

## PART 3: Academic Research

### 3.1 Key Papers: LLM + PCB/Schematic Design

| Paper | Year | Venue | Key Contribution | Link |
|-------|------|-------|-----------------|------|
| **PCBSchemaGen** | 2026 | arXiv | First training-free LLM framework for PCB schematic design. Knowledge Graph from IC datasheets + Subgraph Isomorphism for verification. | [arxiv.org/abs/2602.00510](https://arxiv.org/abs/2602.00510) |
| **PCB-Bench** | 2026 | ICLR 2026 | First comprehensive benchmark for LLMs on PCB placement and routing. Three task settings, three modalities. | [openreview.net](https://openreview.net/pdf/a1fc4fe1f92b72225de5f67cf8f373584b589173.pdf) |
| **CircuitLM** | 2026 | arXiv | Multi-agent pipeline: prompt to CircuitJSON schematic via 5 stages. DMCV evaluation framework. 6 LLMs benchmarked. | [arxiv.org/abs/2601.04505](https://arxiv.org/abs/2601.04505) |
| **SPICEAssistant** | 2025 | arXiv | LLM + SPICE simulation tools for SMPS design. RAG + custom toolkit. 15% to 91% solve rate improvement. | [arxiv.org/abs/2507.10639](https://arxiv.org/abs/2507.10639) |
| **Schemato** | 2024 | arXiv | LLM for netlist-to-schematic conversion. Fine-tuned on human designs. 76% compilation success. | [arxiv.org/abs/2411.13899](https://arxiv.org/abs/2411.13899) |
| **LLM4-IC8K** | 2025 | arXiv | LLM for IC footprint geometry understanding. 71.6% IoU for footprint generation. | [arxiv.org/abs/2508.03725](https://arxiv.org/abs/2508.03725) |
| **EEschematic** | 2025 | GitHub | Multimodal-LLM agent for analog IC schematic generation. SPICE netlist to human-readable schematic. | [github.com/eelab-dev/EEschematic](https://github.com/eelab-dev/EEschematic) |

### 3.2 Surveys

| Paper | Year | Key Content | Link |
|-------|------|------------|------|
| **A Survey of Research in LLMs for EDA** | 2025 | Comprehensive survey of LLM applications across EDA. Model architectures, sizes, customization. Published in ACM TODAES. | [arxiv.org/abs/2501.09655](https://arxiv.org/abs/2501.09655) |
| **The Dawn of Agentic EDA** | 2025 | Evolution from traditional CAD to AI-Native and Agentic design. RTL generation, verification, physical design. | [arxiv.org/html/2512.23189v1](https://arxiv.org/html/2512.23189v1) |
| **Shift-Left Techniques in EDA** | 2025 | AI techniques for prediction and modeling in open-source EDA flows. | [arxiv.org/abs/2509.14551](https://arxiv.org/abs/2509.14551) |
| **ML for EDA: A Survey** | 2021/updated | Foundational survey. ML across all EDA phases. ACM TODAES. | [arxiv.org/abs/2102.03357](https://arxiv.org/abs/2102.03357) |

### 3.3 RL + PCB Routing

| Paper | Year | Approach | Link |
|-------|------|---------|------|
| **GPCB Routing** | 2025 | GPT-based PCB routing method. IEEE TCAD. | IEEE Xplore |
| **Multi-Agent RL PCB Routing** | 2025 | D3QN (Dueling Double Deep Q Network) for multi-agent routing. | [ieeexplore.ieee.org/document/10814351](https://ieeexplore.ieee.org/document/10814351/) |
| **Escape Routing with DRL** | 2025 | Deep Q-Network for escape routing problem. | ADS Harvard |
| **PCBRouteNet** | 2025 | Dynamic network flow model for ML PCB routing dataset generation. ISCAS 2025. | IEEE |
| **OSIRIS** | 2026 | Analog layout dataset generation bridging circuit design and ML. | [arxiv.org/html/2601.19439](https://arxiv.org/html/2601.19439) |

### 3.4 RTL/HDL Generation (Adjacent Domain)

| Paper | Year | Key Contribution | Link |
|-------|------|-----------------|------|
| **AutoEDA** | 2025 | MCP-based LLM agents for RTL-to-GDSII automation. Open source. | [hf.co/papers/2508.01012](https://hf.co/papers/2508.01012) |
| **EDAid** | 2025 | Multi-agent system with ChipLlama fine-tuned models. | [hf.co/papers/2502.10857](https://hf.co/papers/2502.10857) |
| **TuRTLe** | 2025 | Unified LLM evaluation framework for RTL generation. DeepSeek R1 best performer. | [hf.co/papers/2504.01986](https://hf.co/papers/2504.01986) |
| **RealBench** | 2025 | Real-world IP-level Verilog benchmark. o1-preview: 13.3% pass@1. | [hf.co/papers/2507.16200](https://hf.co/papers/2507.16200) |
| **BRIDGES** | 2025 | Graph-enhanced LLM for EDA. 500k+ graph instances, 1.5B tokens. 2-10x improvement. | [hf.co/papers/2504.05180](https://hf.co/papers/2504.05180) |
| **RTL++** | 2025 | Graph representations (CFG/DFG) for RTL code quality. | [hf.co/papers/2505.13479](https://hf.co/papers/2505.13479) |
| **SAGE-HLS** | 2025 | First fine-tuned LLM for HLS code gen. 75% functional correctness. | [hf.co/papers/2508.03558](https://hf.co/papers/2508.03558) |
| **OpenLLM-RTL** | 2025 | Open dataset + benchmark. RTLLM 2.0 (50 designs), RTLCoder-Data (80K samples). | [hf.co/papers/2503.15112](https://hf.co/papers/2503.15112) |

### 3.5 Benchmarks & Evaluation

| Benchmark | Year | Focus | Link |
|-----------|------|-------|------|
| **PCB-Bench** | 2026 | PCB placement + routing with LLMs (ICLR 2026) | OpenReview |
| **CIRCUIT** | 2025 | Circuit interpretation and reasoning. 510 QA pairs. GPT-4o: 48% accuracy. | [arxiv.org/abs/2502.07980](https://arxiv.org/abs/2502.07980) |
| **MMCircuitEval** | 2025 | Multimodal. 3614 questions across full EDA workflow. ICCAD 2025. | [yibolin.com](https://yibolin.com/publications/papers/LLM_ICCAD2025_Zhao.pdf) |
| **AMSbench** | 2025 | Analog/mixed-signal circuit evaluation. | [arxiv.org/abs/2505.24138](https://arxiv.org/abs/2505.24138) |
| **DMCV** | 2026 | Dual-Metric Circuit Validation. Hybrid rule-based + LLM evaluation (0-10 scale). | Part of CircuitLM |

---

## PART 4: Industry Trends

### 4.1 Market Size

- **AI EDA Market 2026:** $4.27 billion
- **AI EDA Market 2032 (projected):** $15.85 billion (24.4% CAGR)
- **Overall EDA Market 2035 (projected):** $34.71 billion
- **Hardware-Assisted Verification Market:** $785.68M (2025) to $3.26B (2035), 15.3% CAGR

### 4.2 Major Vendor AI Strategies

#### Cadence
- **Cerebrus AI Studio:** Agentic AI for SoC implementation. Multi-block, multi-user. 5-10x faster chip delivery. Used in 1000+ tapeouts. Samsung: 4x productivity gain.
- **ChipStack AI Super Agent (2026):** Orchestrates virtual engineers across full Cadence tool suite. Agentic AI + proven optimization AI.
- **Partnership:** Cadence + NVIDIA accelerated engineering solutions for agentic AI chip/system design (2026).

#### Synopsys
- **DSO.ai:** First autonomous AI for chip design. Reinforcement learning for PPA optimization across trillions of design recipes.
- **Synopsys.ai Copilot (2025):** Generative AI assistive + creative capabilities. Days-to-hours, hours-to-minutes acceleration.
- **AgentEngineer (2026):** Agentic framework for autonomous DRC. Estimated 12-month cycle reduction for 2nm chips.
- **NVIDIA:** $2B stake in Synopsys to push GPU-accelerated EDA.

#### Siemens (ex-Mentor)
- **Fuse EDA AI Agent (March 2026, GTC):** Purpose-built autonomous agent for multi-tool orchestration across semiconductor, 3D IC, and PCB workflows. Spans design, verification, manufacturing sign-off.
- **Technical stack:** RAG pipeline, multimodal EDA data lake, custom parsers, NVIDIA Agent Toolkit + Nemotron models.
- **Security:** Role-based access, audit trails, human checkpoints, air-gapped deployment.
- **PCB-specific:** Xpedition + HyperLynx integration for signal integrity, with AI-accelerated solvers.

#### Altium
- **Altium Develop:** Unified environment from requirements to manufacturing. Built on Altium Designer + Altium 365.
- **AI stance:** Positioning AI as productivity assistant rather than autonomous designer. Integration with external AI tools (CELUS, Quilter, Traceformer, BoardMint).
- **No native AI autorouter or generative design** yet in core product.

#### Keysight
- **ADS 2026 AI Assistants:** Chat (learning) + Copilot (tool execution) for RF/high-speed design. On-premises. Included free with ADS subscription.

#### KiCad
- **KiCad 10 (2026-03-20):** No native AI features. Improved Python scripting API enables richer third-party AI plugins.
- **Roadmap:** No announced plans for official AI integration. Community ecosystem is filling the gap (see Part 2).

### 4.3 Key Industry Trends

1. **Agentic EDA is the 2026 theme.** All three major vendors (Cadence, Synopsys, Siemens) launched autonomous AI agents in 2025-2026 that orchestrate multi-tool workflows without human intervention.

2. **"Prompt engineer" replacing GUI interaction.** Natural language interfaces to EDA tools are becoming standard. Siemens Fuse, Synopsys Copilot, Keysight Chat all support conversational design.

3. **MCP (Model Context Protocol) is the integration standard** for AI-tool communication in the open-source world. Multiple KiCad MCP servers exist, and AutoEDA (academic) uses MCP for RTL-to-GDSII.

4. **Reinforcement learning dominates PCB routing.** Quilter, DeepPCB, and multiple papers use RL for placement and routing, outperforming classical autorouters.

5. **Free tiers proliferate.** Quilter, Flux, DeepPCB, BoardMint, CELUS, Traceformer all offer free access to attract users.

6. **On-premises AI is a requirement** for sensitive IP. Keysight, PrimisAI, Siemens Fuse all emphasize air-gapped/on-prem deployment.

7. **Open-source AI EDA is nascent but growing.** Circuit-synth, KiCad MCP servers, kicad-happy, and multiple plugins form an emerging ecosystem, but no single project has achieved critical mass.

---

## PART 5: Datasets & Benchmarks

### 5.1 Schematic/Design Datasets

| Dataset | Size | Format | License | Link |
|---------|------|--------|---------|------|
| **Open Schematics** | ~84,470 circuit schematic samples | KiCad files, images, metadata, component lists | CC-BY-4.0 | [huggingface.co/datasets/bshada/open-schematics](https://huggingface.co/datasets/bshada/open-schematics) |
| **CircuitNet (EDA)** | Large-scale | Congestion/routing prediction data | Open | [github.com/circuitnet/CircuitNet](https://github.com/circuitnet/CircuitNet) |
| **OpenABC-D** | Large-scale | ML-guided IC synthesis | Open | Semantic Scholar |
| **RTLCoder-Data** | 80K instruction-code pairs (7K verified) | Verilog RTL | Open | Part of OpenLLM-RTL |
| **BRIDGES Dataset** | 500K+ graph instances, 1.5B tokens | RTL + netlist graphs | Open (planned) | Part of BRIDGES paper |

### 5.2 PCB Defect/Inspection Datasets

| Dataset | Size | Type | Link |
|---------|------|------|------|
| **DeepPCB** | 1,500 image pairs | 6 defect types | [github.com/tangsanli5201/DeepPCB](https://github.com/tangsanli5201/DeepPCB) |
| **DsPCBSD+** | 10,259 images, 20,276 defects | 9 defect categories | Nature Scientific Data |
| **FICS-PCB** | 31 boards, 77K+ components | Component detection | IACR |
| **PCB-METAL** | 984 images, 123 PCBs | IC/Cap/Res/Inductor detection | Semantic Scholar |
| **PCB-Vision** | 53 PCBs | RGB + Hyperspectral | [arxiv.org/html/2401.06528v1](https://arxiv.org/html/2401.06528v1) |
| **HRIPCB** | 1,386 images | 6 defect types | Kaggle |
| **SolDef_AI** | 1,150 images | Solder joint defects | MDPI |
| **JUHCCR-v1** | 20 component types | Hand-drawn recognition | Nature Scientific Reports |

### 5.3 Circuit Benchmarks for LLMs

| Benchmark | Questions/Tasks | What It Tests | Link |
|-----------|----------------|---------------|------|
| **CIRCUIT** | 510 QA pairs | Analog circuit reasoning | arXiv 2502.07980 |
| **MMCircuitEval** | 3,614 questions | Full EDA workflow, multimodal | ICCAD 2025 |
| **AMSbench** | -- | Analog/mixed-signal | arXiv 2505.24138 |
| **PCB-Bench** | Multiple task settings | PCB placement/routing | ICLR 2026 |
| **DMCV** | Per-design scoring | Structural + electrical validity | Part of CircuitLM |
| **RTLLM 2.0** | 50 designs | RTL generation | Part of OpenLLM-RTL |
| **VerilogEval** | -- | Verilog functional correctness | GitHub |
| **RealBench** | IP-level tasks | Real-world Verilog generation | GitHub IPRC-DIP/RealBench |
| **SPICEAssistant Benchmark** | 269 SMPS tasks | Power supply design with SPICE | arXiv 2507.10639 |

---

## PART 6: Mascarade Integration Opportunities

### 6.1 Mascarade's Current Position

Mascarade is a multi-agent LLM orchestration engine with:
- 13 LLM providers (including a KiCad Router provider)
- MCP client + server (5 tools)
- A2A protocol support
- RLVR scaffold with KiCad DRC reward functions
- Electronics-domain and CAD-domain skills
- ML routing classifier
- Finetune pipeline (SimPO/KTO/GRPO/DAPO)

This is a **unique positioning** in the landscape. No other platform combines multi-agent orchestration, multi-provider LLM routing, MCP integration, AND electronics domain specialization.

### 6.2 Competitive Landscape Mapping

| Capability | Mascarade | Closest Competitor | Gap/Opportunity |
|-----------|-----------|-------------------|-----------------|
| Multi-agent orchestration | Yes (17 routers) | Cadence ChipStack, Siemens Fuse | Those are proprietary, closed, $$$. Mascarade is self-hosted and open. |
| KiCad integration | KiCad Router provider | 6+ KiCad MCP servers | Mascarade could consume any KiCad MCP server as a tool. |
| Electronics domain skills | 2 skills | Circuit-Synth (Claude Code) | Circuit-Synth is more specialized. Mascarade is more general. |
| RLVR with DRC rewards | Scaffold exists | No direct competitor | **Unique**. No one else has DRC-based reward functions for RLHF. |
| Multi-provider routing | 13 providers | LiteLLM (routing only) | Mascarade combines routing + orchestration + domain skills. |
| Self-hosted/on-prem | Yes (Docker, 30+ services) | Keysight (on-prem AI) | Open-source alternative to enterprise on-prem AI EDA. |
| Finetune pipeline | SimPO/KTO/GRPO/DAPO | PrimisAI (on-prem fine-tuning) | Mascarade can finetune on electronics-specific data. |

### 6.3 Concrete Integration Opportunities

#### HIGH PRIORITY -- Immediate Value

1. **Consume KiCad MCP Servers as tools.**
   - Add Seeed-Studio/kicad-mcp-server or lamaalrajih/kicad-mcp as MCP tool sources in Mascarade's MCP client.
   - This gives Mascarade agents the ability to: create KiCad projects, add components, wire schematics, run DRC, generate Gerbers -- all via natural language.
   - Effort: Low. Mascarade already has MCP client infrastructure.

2. **Integrate Traceformer as a validation step.**
   - After an agent generates a schematic (via KiCad MCP), automatically submit it to Traceformer for datasheet-backed validation.
   - Creates a "generate + verify" loop unique in the market.
   - Effort: Medium. Requires Traceformer API integration or KiCad plugin invocation.

3. **Use Open Schematics dataset for fine-tuning.**
   - 84,470 KiCad schematics on Hugging Face (CC-BY-4.0).
   - Train/fine-tune a specialized model for schematic understanding and generation.
   - Feeds directly into Mascarade's existing finetune pipeline.
   - Effort: Medium. Data preprocessing + training run on KXKM-AI (RTX 4090).

#### MEDIUM PRIORITY -- Differentiation

4. **Implement RLVR training loop with KiCad DRC.**
   - The scaffold exists. Complete the training loop:
     - Agent generates schematic/PCB via MCP
     - KiCad DRC provides reward signal
     - GRPO/DAPO updates the model
   - No one else has this. It would be the first DRC-in-the-loop RL system for PCB design.
   - Effort: High. Requires stable KiCad automation + training infrastructure.

5. **Circuit-Synth as Mascarade skill.**
   - Circuit-Synth is open source, Python-based, and uses Claude Code.
   - Wrap circuit-synth as a Mascarade composable skill.
   - Gives agents Python-defined circuit generation + JLCPCB pricing + SPICE simulation.
   - Effort: Medium.

6. **BoardMint integration for automated PCB validation.**
   - Free API for DRC + thermal + signal integrity + EMC.
   - Add as a post-routing validation tool in the agent pipeline.
   - Effort: Low-Medium.

#### LOWER PRIORITY -- Long-Term Strategic

7. **Electronics-specific RAG knowledge base.**
   - Ingest datasheets, application notes, reference designs.
   - Use Mascarade's existing knowledge_base router.
   - Combine with PartGenie-style component search (22M parts).
   - Effort: High (data curation).

8. **Agent-to-Agent (A2A) with external services.**
   - Expose Mascarade's electronics agents via A2A protocol.
   - Other AI systems could request "design me a power supply" from Mascarade.
   - Effort: Medium. A2A infrastructure exists.

9. **Fine-tune on CIRCUIT/MMCircuitEval benchmarks.**
   - Use the 510 (CIRCUIT) and 3,614 (MMCircuitEval) evaluation questions as training/eval data.
   - Measure Mascarade agent performance against published baselines (GPT-4o: 48% on CIRCUIT).
   - Effort: Medium.

10. **Quilter/DeepPCB as routing backends.**
    - Both accept design files and return routed boards.
    - Mascarade could orchestrate: schematic generation (LLM) -> routing (Quilter free tier / DeepPCB credits) -> validation (BoardMint/Traceformer).
    - Creates a full prompt-to-production pipeline.
    - Effort: Medium-High (API integration + workflow orchestration).

### 6.4 Strategic Summary

Mascarade occupies a **white space** in the AI+EDA landscape:

- The enterprise players (Cadence, Synopsys, Siemens) have agentic AI but at enterprise prices, closed ecosystems.
- The startups (Quilter, Flux, DeepPCB) solve one vertical each (routing, browser PCB, cloud routing).
- The open-source KiCad ecosystem has many small tools but no orchestration layer.
- **Mascarade is the missing orchestration layer** that can tie together open-source KiCad tools, free-tier commercial APIs, and specialized fine-tuned models into a coherent, self-hosted, multi-agent electronics design pipeline.

The most impactful near-term action is: **KiCad MCP integration + Open Schematics fine-tuning + Traceformer validation = a generate-verify-iterate loop that no one else offers.**

---

## Sources

### AI PCB Design Startups
- [Quilter](https://www.quilter.ai/)
- [Flux.ai](https://www.flux.ai/)
- [DeepPCB](https://deeppcb.ai/)
- [Circuit Mind](https://www.circuitmind.io/)
- [CELUS](https://www.celus.io/)
- [JITX](https://www.jitx.com/)
- [Circuit-Synth](https://www.circuit-synth.com/)
- [SnapMagic](https://www.snapmagic.com/)
- [PrimisAI RapidGPT](https://primis.ai/)
- [Cirkit Designer](https://www.cirkitstudio.com/)
- [Skimatly](https://www.skimatly.xyz/)
- [GerberGPT](https://gerbergpt.com/)

### AI Validation & Analysis
- [Traceformer](https://traceformer.io/)
- [BoardMint](https://boardmint.io/)
- [Keysight ADS AI](https://www.keysight.com/us/en/lib/resources/miscellaneous/eda-ai.html)

### AI BOM & Supply Chain
- [Luminovo](https://luminovo.com/)
- [PartGenie](https://www.partgenie.ai/)
- [Wizerr BOM Optimizer](https://www.wizerr.ai/bom-optimizer)
- [DigiBull AI](https://digibull.ai/)

### KiCad MCP Servers
- [Seeed-Studio/kicad-mcp-server](https://github.com/Seeed-Studio/kicad-mcp-server)
- [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server)
- [lamaalrajih/kicad-mcp](https://github.com/lamaalrajih/kicad-mcp)
- [circuit-synth/mcp-kicad-sch-api](https://github.com/circuit-synth/mcp-kicad-sch-api)
- [Finerestaurant/kicad-mcp-python](https://github.com/Finerestaurant/kicad-mcp-python)

### KiCad AI Plugins
- [ALT TAB KiCad AI Plugin](https://kicad.alttab.rs/)
- [smarton-empower/Smarton-AI](https://github.com/smarton-empower/smarton-ai)
- [colaco1123/K-AI](https://github.com/colaco1123/K-AI)
- [BWolf-16/Smart-Cat](https://github.com/BWolf-16/Smart-Cat)
- [jochemkroon/KiC-AI](https://github.com/jochemkroon/KiC-AI)
- [aklofas/kicad-happy](https://github.com/aklofas/kicad-happy)
- [jasiek/kicad-llm-plugin](https://github.com/jasiek/kicad-llm-plugin)
- [Monacrylic/image2KiCAD](https://github.com/Monacrylic/image2KiCAD)

### Industry
- [Cadence Cerebrus AI Studio](https://www.cadence.com/en_US/home/tools/digital-design-and-signoff/soc-implementation-and-floorplanning/cadence-cerebrus-ai-studio.html)
- [Cadence ChipStack AI Super Agent](https://www.cadence.com/en_US/home/company/newsroom/press-releases/pr/2026/cadence-unleashes-chipstack-ai-super-agent-pioneering-a-new.html)
- [Synopsys DSO.ai](https://www.synopsys.com/ai/ai-powered-eda/dso-ai.html)
- [Synopsys.ai Copilot](https://news.synopsys.com/2025-09-03-Synopsys-Announces-Expanding-AI-Capabilities-for-its-Leading-EDA-Solutions)
- [Siemens Fuse EDA AI Agent](https://news.siemens.com/en-us/siemens-fuse-eda-ai-agent/)
- [KiCad 10.0.0 Release](https://www.kicad.org/blog/2026/03/Version-10.0.0-Released/)
- [AI EDA Market Report](https://www.marketsandmarkets.com/PressReleases/ai-eda.asp)
- [How The EDA Industry Will Evolve In 2026](https://semiengineering.com/how-the-eda-industry-will-evolve-in-2026/)
- [Open Source EDA in the AI Era](https://bitsbytesgates.com/eda/2026/02/07/OpenSourceEDA_in_AI_Era.html)
- [Flux $37M funding](https://siliconangle.com/2026/02/27/flux-nabs-37m-automate-printed-circuit-board-development-ai/)

### Academic Papers
- [PCBSchemaGen (arXiv 2602.00510)](https://arxiv.org/abs/2602.00510)
- [CircuitLM (arXiv 2601.04505)](https://arxiv.org/abs/2601.04505)
- [SPICEAssistant (arXiv 2507.10639)](https://arxiv.org/abs/2507.10639)
- [Schemato (arXiv 2411.13899)](https://arxiv.org/abs/2411.13899)
- [CIRCUIT Benchmark (arXiv 2502.07980)](https://arxiv.org/abs/2502.07980)
- [AMSbench (arXiv 2505.24138)](https://arxiv.org/abs/2505.24138)
- [LLMs for EDA Survey (arXiv 2501.09655)](https://arxiv.org/abs/2501.09655)
- [Dawn of Agentic EDA (arXiv 2512.23189)](https://arxiv.org/html/2512.23189v1)
- [OSIRIS (arXiv 2601.19439)](https://arxiv.org/html/2601.19439)
- [AutoEDA (HF papers 2508.01012)](https://hf.co/papers/2508.01012)
- [EDAid (HF papers 2502.10857)](https://hf.co/papers/2502.10857)
- [TuRTLe (HF papers 2504.01986)](https://hf.co/papers/2504.01986)
- [RealBench (HF papers 2507.16200)](https://hf.co/papers/2507.16200)
- [BRIDGES (HF papers 2504.05180)](https://hf.co/papers/2504.05180)
- [SAGE-HLS (HF papers 2508.03558)](https://hf.co/papers/2508.03558)
- [OpenLLM-RTL (HF papers 2503.15112)](https://hf.co/papers/2503.15112)

### Datasets
- [Open Schematics (HuggingFace)](https://huggingface.co/datasets/bshada/open-schematics)
- [CircuitNet (GitHub)](https://github.com/circuitnet/CircuitNet)
- [DeepPCB Dataset (GitHub)](https://github.com/tangsanli5201/DeepPCB)
- [AI4EDA Resources](https://ai4eda.github.io/)
- [NVIDIA EDA Research](https://research.nvidia.com/labs/electronic-design-automation/)
