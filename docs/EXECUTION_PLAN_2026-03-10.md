# Plan d'exécution — 11 mars 2026 (v3)

Mis à jour post-session. Mesh P2P live, LLM local opérationnel, Docker rebuild OK.

## État actuel

| Repo | Tests | Providers | Infra | Sync |
|------|-------|-----------|-------|------|
| **mascarade** | 196/196 | 7 (Claude, OpenAI, Mistral, Google, HF, Ollama*, llama_cpp) | P2P mesh 3 nœuds, Docker UP | branch +9, à pusher |
| **Kill_LIFE** | 20/20 | — | PlatformIO installé | synced main |
| **crazy_life** | 34/34 | — | — | poussé GitHub |

*Ollama broken sur macOS Tahoe (Metal bfloat16 bug), llama.cpp le remplace.

### Nœuds P2P actifs
| Nœud | Peer ID | Capabilities | Status |
|------|---------|-------------|--------|
| VM (bootstrap+relay) | QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S | llm-inference, gpu, docker, p2p-relay | UP (systemd) |
| CILS MacBook | QmXG56XMOQRUK3QSXK4Y3O4LBR3NGURQYB | kicad-validation, firmware-build, compute | UP (task handler) |
| Tower | QmLHOEMQ6IV3SY2A27OCTAGZ3UF2IHP4HR | compute, storage | UP (task handler) |
| KXKM-AI | Qm4DS64NDLQ3JASHQJ7VSLPGR25L23X7I3 | audio, media | BLOQUÉ (réseau) |

---

## Axe 1 — Mascarade: production

### ~~P0 — Inférence end-to-end~~ ✅
- [x] Serveur local: /send → Claude pong
- [x] Shim OpenAI: /v1/chat/completions → OK
- [x] LLM local: llama.cpp llama3.2:1b → pong

### ~~P2 — Mesh P2P~~ ✅
- [x] Bootstrap VM avec relay
- [x] Workers CILS + Tower avec task handlers
- [x] Task distribution: 3/3 tâches routées
- [x] Scripts: run_all.sh {start|stop|status|test|inference|full}

### ~~P3 — Docker~~ ✅
- [x] mascarade-core rebuilt + running sur VM
- [x] Prometheus scrape configuré (core:8100)
- [x] /metrics endpoint public

### P1 — Push & CI (à faire)
- [ ] Push mascarade (9 commits)
- [ ] Vérifier CI GitHub Actions

### P4 — Sécurisation (cette semaine)
- [ ] MASCARADE_API_KEY
- [ ] P2P auth reject_unsigned=true
- [ ] KXKM relay (problème réseau Tailscale)
- [ ] Knowledge Base URL

### P5 — Services locaux (en cours)
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
- [ ] esp32_minimal.kicad_sch
- [ ] ERC green + BOM + netlist
- [ ] Snapshot schops

### P3 — Intégrations (semaine 3+)
- [ ] ZeroClaw runtime
- [ ] n8n workflow smoke
- [ ] Compliance iot_wifi_eu e2e
- [ ] CI firmware GitHub Actions

---

## Axe 3 — Crazy_life: runtime & optimisation

### ~~P0 — Publication~~ ✅
- [x] Push GitHub (fix email noreply)

### P1 — Runtime (cette semaine)
- [ ] KILL_LIFE_ROOT dans .envrc
- [ ] npm run dev:all → test complet
- [ ] curl localhost:3100/api/killlife/workflows

### P2 — Optimisations (semaine 2)
- [ ] Code-splitting React.lazy()
- [ ] Tests frontend
- [ ] Sync subtree mascarade/web/

---

## Axe 4 — Écosystème: boucle complète

### P0 — Cycle e2e (semaine 2)
- [ ] crazy_life UI → mascarade API → LLM → résultat
- [ ] mascarade API → Kill_LIFE MCP → résultat

### P1 — Fine-tuning (mois 1)
- [ ] Pipeline Claude teacher → CoreML/GGUF student
- [ ] Dataset mascarade-kicad HuggingFace

### P2 — Monitoring (mois 1)
- [ ] Prometheus alerting
- [ ] Grafana consolidé
- [ ] Langfuse traces

---

## Priorités ordonnées

| # | Action | Effort | Bloqueur? |
|---|--------|--------|-----------|
| 1 | Push mascarade | 1 min | Non |
| 2 | MASCARADE_API_KEY | 5 min | Non |
| 3 | Grafana dashboard import | 15 min | Non |
| 4 | KXKM Tailscale bridge | 30 min | Réseau |
| 5 | PlatformIO + premier build | 30 min | Non |
| 6 | crazy_life dev:all test | 15 min | KILL_LIFE_ROOT |
| 7 | Firmware WiFi scanner | 2-4h | Non |
| 8 | Design KiCad ESP32 | 4-8h | KiCad installé |
| 9 | Cycle e2e | 2h | crazy_life runtime |
| 10 | Fine-tuning local | 1-2 jours | Dataset |
