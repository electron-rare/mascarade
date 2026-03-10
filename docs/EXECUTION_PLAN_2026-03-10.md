# Plan d'exécution — 10 mars 2026 (v2)

Plan mis à jour après résolution des bloqueurs critiques.

## État actuel

| Repo | Tests | Providers | Release | Sync |
|------|-------|-----------|---------|------|
| **mascarade** | 196/196 | 5 actifs (Claude, OpenAI, Mistral, Google, HF) | branche ahead +4 | P2P déployé 4 machines |
| **Kill_LIFE** | 20/20 | — | synced origin/main | compliance OK |
| **crazy_life** | 34/34 | — | mergé main, à pusher | — |

### Résolu ce jour
- [x] Configurer ANTHROPIC_API_KEY + OPENAI_API_KEY
- [x] Fixer les 13 tests cassés mascarade → 196/196
- [x] Implémenter `/v1/chat/completions` (shim OpenAI-compat)
- [x] Implémenter routes device voice (session, player, replies)
- [x] Fix timeout configurable Ollama provider
- [x] Fix finetune pipeline (deploy_alias, import paths)
- [x] Créer/enrichir `specs/constraints.yaml` dans Kill_LIFE
- [x] Installer PyYAML + pytest dans Kill_LIFE venv
- [x] Fix test_mcp_runtime_status.py
- [x] `git pull origin main` Kill_LIFE (+988 lignes, ZeroClaw/n8n)
- [x] Commit vitest v4 + merge crazy_life main
- [x] Valider compliance Kill_LIFE (profile prototype, 5 standards)

---

## Axe 1 — Mascarade: passer en production

### P0 — Valider l'inférence end-to-end (immédiat)
- [ ] Démarrer le serveur: `uv run python -m mascarade.server`
- [ ] Test inférence Claude: `curl -X POST localhost:8100/send -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"ping"}]}'`
- [ ] Test shim OpenAI: `curl -X POST localhost:8100/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"claude-sonnet-4-20250514","messages":[{"role":"user","content":"ping"}]}'`
- [ ] Test streaming: `curl -N localhost:8100/stream -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"raconte une blague"}]}'`

### P1 — Push & CI (immédiat)
- [ ] Push mascarade feat/apple-coreml-runtime-lot (4 commits ahead)
- [ ] Push crazy_life main
- [ ] Vérifier CI GitHub Actions sur les deux repos

### P2 — Activer le mesh P2P (cette semaine)
- [ ] Démarrer node bootstrap sur VM: `ssh root@192.168.0.119` → script P2P
- [ ] Démarrer workers: CILS (210), Tower (120), KXKM-AI
- [ ] Valider: `python scripts/p2p/test_mesh.py` → 4/4 peers
- [ ] Tester task distribution en production (LLM → VM, KiCad → CILS)
- [ ] Créer scripts systemd/launchd pour auto-start des nodes

### P3 — Docker & Observabilité (cette semaine)
- [ ] `docker compose up -d` sur VM (core + api + prometheus + grafana)
- [ ] Importer Grafana dashboard P2P (9 panels)
- [ ] Vérifier Prometheus scrape P2P metrics
- [ ] Tester SSE dashboard: ouvrir `scripts/p2p/dashboard.html` dans navigateur

### P4 — Sécurisation (semaine 2)
- [ ] Configurer MASCARADE_API_KEY dans .env (routes protégées)
- [ ] Activer P2P auth obligatoire (reject_unsigned=true)
- [ ] Configurer relay pour KXKM (Tailscale NAT traversal)
- [ ] Configurer Knowledge Base (MEMOS_BASE_URL ou DOCMOST_BASE_URL)

### P5 — Services locaux (quand dispo)
- [ ] Apple CoreML: vérifier service :8201 + activer APPLE_LLM_ENABLED
- [ ] Ollama: vérifier service :11434 + activer OLLAMA_ENABLED
- [ ] Test routing local: strategy=cheapest → Ollama, strategy=best → Claude

---

## Axe 2 — Kill_LIFE: première implémentation réelle

### P0 — Toolchain firmware (cette semaine)
- [ ] Installer PlatformIO: `pip install platformio`
- [ ] Valider build natif: `pio run -e native`
- [ ] Valider tests Unity: `pio test -e native`

### P1 — Premier firmware fonctionnel (semaine 1-2)
- [ ] Spec: WiFi scanner ESP32 (intake → spec → arch → plan)
- [ ] Implémenter dans `firmware/src/main.cpp`
- [ ] Tests Unity: `firmware/test/test_wifi_scan.cpp`
- [ ] Build ESP32: `pio run -e esp32s3_arduino`
- [ ] Passer Gate S0 → S1

### P2 — Premier design KiCad (semaine 2-3)
- [ ] Créer `hardware/esp32_minimal/esp32_minimal.kicad_sch`
- [ ] Design: ESP32-S3-WROOM + USB-C + LDO 3.3V + LEDs status
- [ ] Valider: ERC green, BOM exporté, netlist exporté
- [ ] Snapshot before/after via schops

### P3 — Intégrations avancées (semaine 3+)
- [ ] Installer ZeroClaw runtime
- [ ] Tester n8n workflow smoke (tools/ai/integrations/n8n/)
- [ ] Compliance profile iot_wifi_eu end-to-end
- [ ] CI firmware dans GitHub Actions
- [ ] Evidence packs automatisés

---

## Axe 3 — Crazy_life: publier et optimiser

### P0 — Publication (immédiat)
- [ ] `git push origin main`
- [ ] Valider `npm run release:check` passe
- [ ] Vérifier CI GitHub Actions

### P1 — Configuration runtime (immédiat)
- [ ] Exporter `KILL_LIFE_ROOT=/Users/electron/Kill_LIFE`
- [ ] Tester `npm run dev:all` → frontend + API fonctionnels
- [ ] Valider: `curl localhost:3100/api/killlife/workflows`

### P2 — Optimisations (semaine 2)
- [ ] Code-splitting React.lazy() (CrazyLaneEditor, ComfyUI, Infrastructure)
- [ ] Tests frontend (Dashboard, CrazyLane)
- [ ] Sync subtree mascarade/web/ ← crazy_life

---

## Axe 4 — Écosystème: boucle complète

### P0 — Cycle end-to-end (semaine 2)
- [ ] crazy_life UI → mascarade API → LLM inference → résultat affiché
- [ ] crazy_life CrazyLane → Kill_LIFE workflow → local execution → evidence
- [ ] mascarade API → Kill_LIFE MCP (validate-specs, kicad) → résultat

### P1 — Fine-tuning (mois 1)
- [ ] Pipeline: teacher (Claude) → student (CoreML/GGUF)
- [ ] Dataset: mascarade-kicad (HuggingFace)
- [ ] Valider modèle fine-tuné comme provider local

### P2 — Monitoring & alerting (mois 1)
- [ ] Prometheus alerting: peer_count < expected
- [ ] Grafana: dashboard consolidé (LLM + P2P + cluster)
- [ ] Langfuse: traces agent end-to-end

---

## Priorités ordonnées

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Valider inférence end-to-end | 10 min | Déblocage complet |
| 2 | Push mascarade + crazy_life | 5 min | CI + collaboration |
| 3 | Démarrer mesh P2P 5 nodes | 30 min | Multi-machine actif |
| 4 | Docker compose + Grafana | 1h | Observabilité |
| 5 | Installer PlatformIO | 10 min | Déblocage firmware Kill_LIFE |
| 6 | Premier firmware WiFi scan | 2-4h | Première valeur produit |
| 7 | Premier design KiCad | 4-8h | Pipeline hardware |
| 8 | Cycle e2e crazy→mascarade→kill | 2h | Preuve écosystème |
| 9 | Fine-tuning local | 1-2 jours | Autonomie locale |
| 10 | ZeroClaw + n8n | 1 jour | Runtime autonome |
