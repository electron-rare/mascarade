# Plan d'exécution — 11 mars 2026 (v8)

Statut suite:
- type: `historical-reference`
- source active: `docs/EXECUTION_HUB.md`
- regle: plan archive, a ne pas utiliser comme backlog actif

Mis à jour post-session 3. Pipeline complet (8 agents), DPO, 235/235 tests.

## État actuel

| Repo | Tests | Providers | Infra | Sync |
|------|-------|-----------|-------|------|
| **mascarade** | 235/235 | 7 (Claude, OpenAI, Mistral, Google, HF, Ollama*, llama_cpp) | P2P mesh 5 nœuds, Docker UP | branch +many, à pusher |
| **Kill_LIFE** | 20/20 | — | PlatformIO à installer | synced main |
| **crazy_life** | 34/34 | — | — | poussé GitHub |

*Ollama broken sur macOS Tahoe (Metal bfloat16 bug), llama.cpp le remplace.

### Nœuds P2P actifs (capabilities vérifiées 11/03)
| Nœud | Role | Capabilities | Status | Finetune |
|------|------|-------------|--------|----------|
| VM (bootstrap) :4002 | infra | docker, p2p-relay, compute | UP (systemd) | deployed |
| GrosMac (bridge) :4001 | bridge | p2p-relay, p2p-bridge, llm-inference, ft-research, ft-teacher | UP (local) | local |
| CILS MacBook :4001 | worker | compute, ft-validation | UP (task handler) | deployed |
| Tower :4001 | worker | compute, storage, ft-archive | UP (task handler) | deployed |
| KXKM-AI :4001 | worker | llm-inference, gpu, compute, ft-student | UP (via relay) | deployed |

### Fine-tuning agents (créés 11/03)
| Agent | Module | Status |
|-------|--------|--------|
| Chercheur (Researcher) | `mascarade.finetune.agents.researcher` | Testé OK — HF Hub search |
| Documentaliste | `mascarade.finetune.agents.documentalist` | Testé OK — HF datasets |
| Doctor (Teacher) | `mascarade.finetune.agents.teacher` | Créé — nécessite Router |
| Archiviste | `mascarade.finetune.agents.archivist` | Créé — nécessite HF token |
| Student | `mascarade.finetune.agents.student` | Créé — nécessite trl/peft ou llama.cpp |
| Analyste | `mascarade.finetune.agents.analyst` | Créé — nécessite llama-cli |
| Renforceur | `mascarade.finetune.agents.reinforcer` | Créé — nécessite Teacher + Student |
| Validateur | `mascarade.finetune.agents.validator` | Créé — nécessite llama-cli |
| Orchestrateur | `mascarade.finetune.orchestrator` | Créé — orchestre pipeline complet |
| Registry | `mascarade.finetune.registry` | Testé OK — JSON local |
| P2P handlers | `mascarade.finetune.p2p.task_handlers` | Créé — route vers agents |
| P2P capabilities | `mascarade.finetune.p2p.capabilities` | Créé — mapping nœud/rôle |

---

## Axe 1 — Mascarade: production

### ~~P0 — Inférence end-to-end~~ ✅
### ~~P2 — Mesh P2P~~ ✅
### ~~P3 — Docker~~ ✅

### ~~P2bis — Bridge KXKM~~ ✅
- [x] GrosMac bridge entre LAN (192.168.0.x) et Tailscale (100.x)
- [x] KXKM bootstraps vers bridge via Tailscale IP 100.80.178.42:4001
- [x] P2PRelay actif pour NAT traversal

### ~~P2ter — Capabilities audit~~ ✅
- [x] VM: docker, p2p-relay, compute (6.8GB RAM, 4 CPU, NO GPU)
- [x] CILS: compute (MacBook, pas de KiCad/PlatformIO)
- [x] KXKM: llm-inference, gpu, compute, ft-student (RTX 4090 24GB, 62GB RAM, 28 CPU)
- [x] Tower: compute, storage
- [x] GrosMac: p2p-relay, p2p-bridge, llm-inference

### ~~P6 — WebUI contrôle~~ ✅
- [x] Page P2P Mesh: topologie live, status nœuds, capabilities map
- [x] Page Fine-Tuning: 8 agents pipeline, registry modèles/datasets/runs
- [x] Routes API: /api/p2p/* + /api/finetune/*
- [x] Navigation: section "P2P & Training" dans sidebar
- [x] Build frontend + API OK

### ~~P7 — TUI scripts~~ ✅
- [x] mesh_tui.py: status/start/stop nœuds depuis terminal
- [x] finetune tui.py: recherche HF, registre, status mesh
- [x] run_research.py: CLI recherche modèles + datasets

### ~~P8 — KXKM-AI GPU setup~~ ✅
- [x] venv créé + pip install torch+cu124, trl, peft, bitsandbytes
- [x] RTX 4090 validée: torch.cuda.is_available() = True

### P1 — Push & CI (à faire)
- [ ] Push mascarade (many commits incl. finetune + webui)
- [ ] Vérifier CI GitHub Actions

### P4 — Sécurisation (cette semaine)
- [x] MASCARADE_API_KEY dans .env
- [ ] P2P auth reject_unsigned=true
- [ ] Knowledge Base URL

### P5 — Services locaux
- [x] llama.cpp: provider actif, llama3.2:1b
- [ ] Ollama: broken macOS Tahoe — attendre update
- [ ] Apple CoreML: non vérifié

---

## Axe 2 — Kill_LIFE: première implémentation

### P0 — Toolchain firmware (cette semaine)
- [ ] `pip install platformio`
- [ ] `pio run -e native && pio test -e native`

### P1 — Premier firmware WiFi scanner (semaine 1-2)
- [ ] Spec: intake → spec → arch → plan
- [ ] Implémenter firmware/src/main.cpp
- [ ] Tests Unity
- [ ] Build ESP32: pio run -e esp32s3_arduino
- [ ] Gate S0 → S1

### P2 — Premier design KiCad (semaine 2-3)
### P3 — Intégrations (semaine 3+)

---

## Axe 3 — Crazy_life: runtime & optimisation

### ~~P0 — Publication~~ ✅

### P1 — Runtime (cette semaine)
- [ ] KILL_LIFE_ROOT dans .envrc
- [ ] npm run dev:all → test complet
- [ ] curl localhost:3100/api/killlife/workflows

### P2 — Optimisations (semaine 2)

---

## Axe 4 — Fine-tuning distribué P2P

### ~~P0 — Architecture agents~~ ✅
- [x] 8 agents spécialisés créés (researcher → validator)
- [x] Registry local JSON (~/.mascarade/finetune/registry.json)
- [x] Orchestrateur pipeline complet
- [x] P2P task handlers pour distribution
- [x] Mapping capabilities → machines

### P1 — Activation agents (cette semaine)
- [ ] Installer huggingface_hub sur toutes les machines
- [x] Connecter Teacher agent au mascarade Router
- [ ] Installer trl + peft sur KXKM-AI (ft-student)
- [ ] Tester pipeline research → dataset → training sur mesh
- [ ] Premier fine-tune: Qwen2.5-0.5B-Instruct sur code-generation

### P2 — Pipeline complet (semaine 2)
- [ ] Teacher data generation via Claude (strategy=BEST)
- [ ] LoRA training sur KXKM-AI (RTX 4090)
- [ ] Evaluation + benchmarks (Analyste)
- [ ] DPO cycle (Renforceur)
- [ ] Validation + red-teaming (Validateur sur CILS)
- [ ] Publication HuggingFace (Archiviste)

### P3 — Automatisation (semaine 3)
- [ ] Cycle continu: recherche hebdo nouvelles bases
- [ ] Auto-registration provider post-fine-tune
- [ ] Dataset mascarade-kicad sur HuggingFace

---

## Axe 5 — Écosystème: boucle complète

### P0 — Cycle e2e (semaine 2)
- [ ] crazy_life UI → mascarade API → LLM → résultat
- [ ] mascarade API → Kill_LIFE MCP → résultat

### P1 — Monitoring (mois 1)
- [ ] Grafana dashboard P2P
- [ ] Prometheus alerting: peer_count < expected
- [ ] Langfuse traces agents e2e

---

## Priorités ordonnées

| # | Action | Effort | Bloqueur? |
|---|--------|--------|-----------|
| 1 | Push mascarade (incl. finetune) | 1 min | Non |
| 2 | Activer ft-research sur mesh | 30 min | huggingface_hub |
| 3 | Installer trl/peft sur KXKM-AI | 30 min | SSH KXKM |
| 4 | Premier fine-tune Qwen2.5 | 2h | trl + dataset |
| 5 | PlatformIO + premier build | 30 min | Non |
| 6 | crazy_life dev:all test | 15 min | KILL_LIFE_ROOT |
| 7 | P2P auth reject_unsigned | 15 min | Non |
| 8 | Grafana dashboard import | 15 min | Non |
| 9 | Teacher data gen (Claude) | 2h | Router + API keys |
| 10 | DPO cycle + validation | 4h | Training complete |
