# TODO Consolidation — Raw Extraction (16 mars 2026)

Extraction automatisée de tous les items ouverts (`- [ ]`) des 7 fichiers TODO + plan d'exécution.
Total: **117 items ouverts** répartis sur 8 fichiers source.

---

## Statistiques par fichier source

| Fichier | Items ouverts | Dernière MAJ | Domaine principal |
|---------|--------------|--------------|-------------------|
| `docs/EXECUTION_PLAN_2026-03-10.md` | 34 | 2026-03-11 | Multi-axes global |
| `docs/TODO_2026-03-10.md` | 26 | 2026-03-13 | Global (v10) |
| `TODO_AI_NOVEL_ENGINE.md` | 17 | 2026-03-14 | AI Novel Engine / Apple runtime |
| `TODO_TUNNING_PARTY.md` | 11 | 2026-03-09 | Fine-tuning pipeline |
| `TODO_COCKPIT_OPS.md` | 10 | 2026-03-08 | Cockpit / Ops / Observability |
| `TODO_VM.md` | 9 | 2026-03-09 | VM / Infra |
| `TODO_IMPLEMENTE.md` | 7 | 2026-03-06 | Fine-tuning reference |
| `TODO_CAD_KICAD.md` | 3 | 2026-03-07 | CAD / KiCad |

---

## Items ouverts par domaine

### CORE — LLM Router / Providers / Agents (6 items)

| # | Item | Source | Priority | Stale? | Notes |
|---|------|--------|----------|--------|-------|
| C1 | Fixer Ollama macOS (update ou rester sur llama.cpp) | TODO_2026-03-10 | IMMÉDIAT | ⚠️ Possibly stale | Metal bfloat16 bug on macOS Tahoe — may be fixed in newer Ollama |
| C2 | Apple CoreML provider | TODO_2026-03-10 | S3+ | Non | Provider file exists (`apple_coreml.py`), but not verified |
| C3 | Ollama: broken macOS Tahoe — attendre update | EXEC_PLAN | P5 | ⚠️ Duplicate of C1 | Same as C1 |
| C4 | Apple CoreML: non vérifié | EXEC_PLAN | P5 | ⚠️ Duplicate of C2 | Same as C2 |
| C5 | Ajouter GRPO dans ReinforcerAgent | TODO_2026-03-10 | S2 | Non | reasoning, 5GB VRAM min |
| C6 | Auto-registration: modèle fine-tuné → provider mascarade | TODO_2026-03-10 | S2 | Non | |

### API — Routes / Gateway (0 items)

Aucun item ouvert spécifique à l'API gateway.

### WEB — Frontend / Cockpit (0 items)

Aucun item ouvert spécifique au frontend (tous les items cockpit sont dans TODO_COCKPIT_OPS).

### FINETUNE — Pipeline / Training / Datasets (30 items)

| # | Item | Source | Priority | Stale? | Notes |
|---|------|--------|----------|--------|-------|
| F1 | Tester distribute_task ft-research → GrosMac → résultats HF | TODO_2026-03-10 | Cette semaine | Non | P2P-based research distribution |
| F2 | Analyste: benchmarks perplexité + vitesse (HumanEval) | TODO_2026-03-10 | Cette semaine | Non | |
| F3 | Archiviste: push résultat sur HuggingFace clemsail/ | TODO_2026-03-10 | Cette semaine | Non | |
| F4 | Pipeline fine-tune via P2P distribute_task (pas SSH manuel) | TODO_2026-03-10 | Cette semaine | Non | |
| F5 | DPO/SimPO cycle: Renforceur collecte erreurs → Teacher corrige → Student re-train | TODO_2026-03-10 | S2 | Non | |
| F6 | Validation: red-team + regression sur CILS | TODO_2026-03-10 | S2 | Non | |
| F7 | Publication: Archiviste push modèle final validé | TODO_2026-03-10 | S2 | Non | Duplicate of F3 |
| F8 | Cycle continu: recherche hebdo nouvelles bases/datasets | TODO_2026-03-10 | S3+ | Non | |
| F9 | Dataset mascarade-kicad sur HuggingFace | TODO_2026-03-10 | S3+ | Non | |
| F10 | Cycle e2e: crazy_life → mascarade API → Kill_LIFE MCP → résultat | TODO_2026-03-10 | S3+ | 🔗 Cross-repo | Depends on crazy_life + Kill_LIFE |
| F11 | Mesurer si 2 trainings GPU parallèles apportent un gain réel sur Quadro P2000 | TODO_IMPLEMENTE | Backlog | ⚠️ Stale | References Quadro P2000 — benchmark already done on RTX 4090 |
| F12 | Identifier précisément le périmètre Agent Zero visé ici | TODO_IMPLEMENTE | Backlog | Non | Agent Zero scoping |
| F13 | Comparer Agent Zero avec l'orchestrateur local | TODO_IMPLEMENTE | Backlog | Non | |
| F14 | Définir si Agent Zero sert à: orchestration/planification/supervision/expérimentation | TODO_IMPLEMENTE | Backlog | Non | |
| F15 | Faire un POC isolé Agent Zero | TODO_IMPLEMENTE | Backlog | Non | |
| F16 | Évaluer le coût de maintenance Agent Zero avant intégration | TODO_IMPLEMENTE | Backlog | Non | |
| F17 | Définir les garde-fous Agent Zero (secrets, CPU/GPU, timeout, logs) | TODO_IMPLEMENTE | Backlog | Non | |
| F18 | Approuver ou rejeter mascarade-components-review après revue humaine | TODO_TUNNING | Backlog | Non | Appears 3x across files |
| F19 | Évaluer Agent Zero hors pipeline critique | TODO_TUNNING | Backlog | Non | Duplicate of F12-F17 |
| F20 | Benchmarker candidats veille web: Qwen3-Coder-Next, Mellum-4b, DeepSeek-V3.2 | TODO_TUNNING | Backlog | Non | Also in TODO_2026-03-10 |
| F21 | Refaire benchmark GPU sur classe plus contrainte si disponible | TODO_TUNNING | Backlog | ⚠️ Low priority | |
| F22 | Phase A: attendre completion (~22h) | TODO_TUNNING | Immédiat | ⚠️ Possibly stale | Was written 2026-03-09, likely completed by now |
| F23 | Phase B: rejection sampling (après Phase A) | TODO_TUNNING | Next | Non | gcc-arm-none-eabi, ngspice requis |
| F24 | Phase C: DPO training (après Phase B) | TODO_TUNNING | Next | Non | |
| F25 | Phase D: publication HF adapters sous clemsail/mascarade-*-lora | TODO_TUNNING | Next | Non | |
| F26 | Repeupler finetune/kicad_mcp_server/ | TODO_TUNNING | Backlog | ⚠️ Stale | Directory exists but package.json missing |
| F27 | Surveiller Qwen3-Coder-Next (annonce mars 2026) | TODO_2026-03-10 | S2 | Non | |
| F28 | Installer huggingface_hub sur toutes les machines | EXEC_PLAN | P1 | ⚠️ Possibly done | Already in core deps |
| F29 | Tester pipeline research → dataset → training sur mesh | EXEC_PLAN | P1 | Non | |
| F30 | Premier fine-tune: Qwen2.5-0.5B-Instruct sur code-generation | EXEC_PLAN | P1 | ⚠️ Done | Already done (see FAIT in TODO_2026-03-10) |

### INFRA — Docker / VM / Monitoring / P2P (28 items)

| # | Item | Source | Priority | Stale? | Notes |
|---|------|--------|----------|--------|-------|
| I1 | Grafana dashboard P2P import | TODO_2026-03-10 | Cette semaine | Non | Appears 3x across files |
| I2 | P2P auth reject_unsigned=true sur tous les nœuds | TODO_2026-03-10 | Cette semaine | Non | Code exists in auth.py but not enabled. Appears 3x |
| I3 | Knowledge Base URL configurée | TODO_2026-03-10 | Cette semaine | Non | knowledge_base.py exists |
| I4 | Graphiti MCP Server sur VM (knowledge graph) | TODO_2026-03-10 | Cette semaine | Non | Graphiti referenced in mcp/client.py |
| I5 | Registry-first MCP: décider si firecrawl doit être ajouté | TODO_2026-03-10 | Cette semaine | Non | |
| I6 | Registry-first MCP: décider si mem0 doit être ajouté | TODO_2026-03-10 | Cette semaine | Non | |
| I7 | Registry-first MCP: appliquer shadow config sur ~/.codex/config.toml | TODO_2026-03-10 | Cette semaine | Non | |
| I8 | Prometheus alerting: peer_count < expected | TODO_2026-03-10 | S2 | Non | |
| I9 | Grafana consolidé: LLM + P2P + finetune metrics | TODO_2026-03-10 | S2 | Non | Overlap with I1 |
| I10 | Langfuse traces agents e2e | TODO_2026-03-10 | S2 | Non | Langfuse already connected per COCKPIT_OPS |
| I11 | ZeroClaw + n8n integration | TODO_2026-03-10 | S3+ | Non | |
| I12 | Machine dispatch: utiliser current_machine_context.sh + chain_next_lot.sh | TODO_VM | Backlog | Non | Awaits another machine |
| I13 | Câbler premiers jobs réels vers mascarade-ops/jobs/watch | TODO_VM | Backlog | Non | |
| I14 | Préparer phase 2 distante (SearXNG, Paperless-ngx, Karakeep) | TODO_VM | Backlog | Non | Also in COCKPIT_OPS |
| I15 | Renseigner ANTHROPIC_API_KEY + OPENAI_API_KEY sur machine | TODO_VM | Sécurité | Non | |
| I16 | Garder secrets hors fichiers versionnés | TODO_VM | Sécurité | Non | |
| I17 | Installer Docling dans venv tools (opt-in) | TODO_VM | Opt-in | Non | |
| I18 | Installer openai-whisper dans venv tools (opt-in) | TODO_VM | Opt-in | Non | |
| I19 | Revalider règle hôte DOCKER-USER pour 80/tcp, 3500/tcp, 5001/tcp | TODO_VM | Réseau | Non | |
| I20 | Définir chemin edge-proxy pour TLS si exposition publique | TODO_VM | Réseau | Non | |
| I21 | Push mascarade (many commits) | EXEC_PLAN | P1 | Non | |
| I22 | Vérifier CI GitHub Actions | EXEC_PLAN | P1 | Non | |
| I23 | Grafana dashboard P2P (EXEC_PLAN) | EXEC_PLAN | Mois 1 | ⚠️ Dup of I1 | |
| I24 | Prometheus alerting peer_count (EXEC_PLAN) | EXEC_PLAN | Mois 1 | ⚠️ Dup of I8 | |
| I25 | Langfuse traces agents e2e (EXEC_PLAN) | EXEC_PLAN | Mois 1 | ⚠️ Dup of I10 | |
| I26 | PlatformIO pip install + pio run/test | EXEC_PLAN | P0 Kill_LIFE | 🔗 Cross-repo | Kill_LIFE toolchain |
| I27 | Sujets externes: billing Anthropic, activation API Google, quota NEXAR | COCKPIT_OPS | Externe | Non | |
| I28 | K-012 si host-native KiCad redevient requis | COCKPIT_OPS | Conditionnel | Non | |

### EXTERNAL — Cross-repo (crazy_life / Kill_LIFE) (12 items)

| # | Item | Source | Priority | Stale? | Notes |
|---|------|--------|----------|--------|-------|
| X1 | KILL_LIFE_ROOT dans .envrc | EXEC_PLAN | P1 | 🔗 Cross-repo | crazy_life runtime |
| X2 | npm run dev:all → test complet | EXEC_PLAN | P1 | 🔗 Cross-repo | crazy_life |
| X3 | curl localhost:3100/api/killlife/workflows | EXEC_PLAN | P1 | 🔗 Cross-repo | crazy_life |
| X4 | Spec firmware WiFi scanner (intake → spec → arch → plan) | EXEC_PLAN | P1 Kill_LIFE | 🔗 Cross-repo | Kill_LIFE |
| X5 | Implémenter firmware/src/main.cpp | EXEC_PLAN | P1 Kill_LIFE | 🔗 Cross-repo | |
| X6 | Tests Unity Kill_LIFE | EXEC_PLAN | P1 Kill_LIFE | 🔗 Cross-repo | |
| X7 | Build ESP32: pio run -e esp32s3_arduino | EXEC_PLAN | P1 Kill_LIFE | 🔗 Cross-repo | |
| X8 | Gate S0 → S1 Kill_LIFE | EXEC_PLAN | P1 Kill_LIFE | 🔗 Cross-repo | |
| X9 | Teacher data gen via Claude (strategy=BEST) | EXEC_PLAN | P2 | Non | |
| X10 | LoRA training sur KXKM-AI (RTX 4090) | EXEC_PLAN | P2 | ⚠️ Already done | Done per TODO_2026-03-10 FAIT |
| X11 | Verrouiller contrat R-010 multi-repo sync crazy_life/Kill_LIFE/llmfit | TODO_IMPLEMENTE | Backlog | 🔗 Cross-repo | |
| X12 | Backlog MCP canonique: Kill_LIFE/specs/mcp_tasks.md | TODO_VM ref | Ref | 🔗 Cross-repo | |

### COCKPIT / OPS — Observability (7 items)

| # | Item | Source | Priority | Stale? | Notes |
|---|------|--------|----------|--------|-------|
| O1 | Étendre Grafana si nouveau domaine justifie | COCKPIT_OPS | Conditionnel | Non | |
| O2 | Recueillir retours UX à froid sur Logs et OpsHub | COCKPIT_OPS | Conditionnel | Non | |
| O3 | Étendre actions opérateur Agent Zero si usage dépasse copilot | COCKPIT_OPS | Conditionnel | Non | |
| O4 | Étendre stack phase2 (SearXNG, Paperless-ngx, Karakeep) si workflow justifie | COCKPIT_OPS | Conditionnel | Non | Dup of I14 |
| O5 | Étendre cockpit industriel si besoin dépasse inventaire actuel | COCKPIT_OPS | Conditionnel | Non | |
| O6 | Rouvrir DCS live externe avec vrai runtime OT | COCKPIT_OPS | Conditionnel | Non | |
| O7 | Rebrancher AgentSight si besoin opérateur réapparaît | COCKPIT_OPS | Optionnel | Non | AgentSight ref in web/Logs.tsx |

### CAD / KiCad (3 items)

| # | Item | Source | Priority | Stale? | Notes |
|---|------|--------|----------|--------|-------|
| K1 | Intégrer stack CAD dans docker-compose.yml principal | CAD_KICAD | Hors scope | Non | |
| K2 | Exposer serveur MCP KiCad sur transport HTTP réseau | CAD_KICAD | Hors scope | Non | |
| K3 | Ajouter UI cockpit pour piloter stack CAD | CAD_KICAD | Hors scope | Non | |

### AI NOVEL ENGINE (17 items)

| # | Item | Source | Priority | Stale? | Notes |
|---|------|--------|----------|--------|-------|
| N1 | Garder installation Apple de 3 modèles comme prérequis ANE | AI_NOVEL | P0 | Non | |
| N2 | Finir lot baselines pour qwen2.5-0.5b et qwen2.5:1.5b | AI_NOVEL | P0 | Non | |
| N3 | Stabiliser second modèle local autour de la ref Apple 4B (cible: ollama:qwen2.5:7b) | AI_NOVEL | P0 | Non | |
| N4 | Faire passer cycle run_next_lots.py --lot priority_models | AI_NOVEL | P1 | Non | |
| N5 | Rendre explicite runtime Apple: un seul model_id servi à la fois | AI_NOVEL | P1 | Non | |
| N6 | Fixer crash Metal host ollama natif avec qwen2.5:1.5b | AI_NOVEL | P1 | Non | Related to C1 |
| N7 | stateful-mistral7b-instruct-int4-coreml: smoke bloqué > 8 min | AI_NOVEL | P1 Bloqué | Non | |
| N8 | ollama:qwen2.5:7b reste quality_blocked sur outline_like | AI_NOVEL | P1 Bloqué | Non | |
| N9 | apple-coreml:qwen2.5-0.5b demande switch runtime explicite | AI_NOVEL | P1 Bloqué | Non | |
| N10 | ollama:qwen2.5:1.5b reste à requalifier après lot baselines | AI_NOVEL | P1 Bloqué | Non | |
| N11 | Host ollama natif 0.17.7 erreur Metal sur qwen2.5:1.5b | AI_NOVEL | P1 Bloqué | Non | Dup of N6 |
| N12 | Runtime Apple local: un seul model_id à la fois sur :8201 | AI_NOVEL | P1 Bloqué | Non | Dup of N5 |
| N13 | Garder apple-coreml:qwen3.5-4b comme ref ANE | AI_NOVEL | P0 Prochain | Non | |
| N14 | Garder ollama Docker CPU comme ref pour candidats Ollama | AI_NOVEL | P0 Prochain | Non | |
| N15 | Exposer contrainte "un seul modèle Apple" dans runbooks | AI_NOVEL | P1 Prochain | Non | Dup of N5/N12 |
| N16 | Laisser ai-novel-engine finir baselines, puis rejouer ollama:qwen2.5:7b | AI_NOVEL | P1 Prochain | Non | |
| N17 | Requalifier qwen2.5-0.5b et qwen2.5:1.5b en baselines vitesse | AI_NOVEL | P1 Prochain | Non | |

---

## Résumé des items dupliqués identifiés

| Thème | Occurrences | Fichiers | Item canonique |
|-------|------------|----------|----------------|
| Grafana dashboard P2P | 3 | TODO_2026-03-10, EXEC_PLAN, COCKPIT_OPS | I1 |
| P2P auth reject_unsigned=true | 3 | TODO_2026-03-10, EXEC_PLAN, TODO_VM | I2 |
| Langfuse traces agents e2e | 2 | TODO_2026-03-10, EXEC_PLAN | I10 |
| Prometheus alerting peer_count | 2 | TODO_2026-03-10, EXEC_PLAN | I8 |
| Archiviste push HF | 2 | TODO_2026-03-10 (S1 + S2) | F3 |
| Approuver mascarade-components-review | 3 | TODO_TUNNING (×2), TODO_2026-03-10 | F18 |
| Agent Zero évaluation | 5+ | TODO_IMPLEMENTE (×6), TODO_TUNNING, COCKPIT_OPS | F12-F17 |
| Phase 2 SearXNG/Paperless/Karakeep | 2 | TODO_VM, COCKPIT_OPS | I14 |
| Benchmarker candidats veille web | 2 | TODO_TUNNING, TODO_2026-03-10 | F20 |
| Ollama macOS fix | 2 | TODO_2026-03-10, EXEC_PLAN | C1 |
| Apple CoreML provider | 2 | TODO_2026-03-10, EXEC_PLAN | C2 |
| Runtime Apple un seul modèle | 3 | AI_NOVEL (N5, N12, N15) | N5 |

**Total duplicates identifiés:** ~30 items qui sont des doublons inter-fichiers.
**Items uniques réels estimés:** ~87 (117 - 30 duplicates).

---

## Items potentiellement stales

| Item | Raison | Évidence |
|------|--------|----------|
| F11 — Benchmark GPU parallèle sur Quadro P2000 | Benchmark déjà fait sur RTX 4090 (résultat: speedup 1.857x) | TODO_TUNNING §4 profils machine |
| F22 — Phase A: attendre completion (~22h) | Écrit le 2026-03-09, 7 jours passés | Probablement terminé |
| F28 — Installer huggingface_hub sur toutes les machines | Déjà dans les deps core (uv add) et déployé sur 4 machines | TODO_2026-03-10 FAIT section |
| F30 — Premier fine-tune Qwen2.5-0.5B | Déjà réalisé: loss 2.98→1.93, 22s sur KXKM-AI | TODO_2026-03-10 FAIT section |
| X10 — LoRA training sur KXKM-AI | Déjà fait: fine-tune #2, 1.5B + Magicoder, 337s, loss 0.5463 | TODO_2026-03-10 FAIT section |
| F26 — Repeupler kicad_mcp_server/ | Le directory existe mais `package.json` manque toujours | Vérifié: `ls finetune/kicad_mcp_server/package.json` = MISSING |

---

## Dépendances cross-repo

| Item | Repos concernés | Type de dépendance |
|------|----------------|-------------------|
| F10 — Cycle e2e crazy_life → mascarade → Kill_LIFE MCP | crazy_life, Kill_LIFE, mascarade | Runtime integration |
| X1-X3 — crazy_life runtime & test | crazy_life | KILL_LIFE_ROOT env var |
| X4-X8 — Kill_LIFE firmware | Kill_LIFE | PlatformIO toolchain |
| X11 — Contrat R-010 multi-repo sync | crazy_life, Kill_LIFE, llmfit | Sync contract |
| X12 — Backlog MCP canonique | Kill_LIFE/specs/mcp_tasks.md | Reference only |
| I26 — PlatformIO install + test | Kill_LIFE | Toolchain setup |
| TODO_VM ref — Backlog cockpit/release | crazy_life/plan.md | Reference only |

---

## Répartition par priorité (items uniques, sans duplicates)

| Priorité | Count | Domaines |
|----------|-------|----------|
| P0 / IMMÉDIAT | 8 | Core (Ollama fix), AI Novel Engine (3 models), Push |
| P1 / Cette semaine | 15 | Infra (P2P auth, KB URL, Grafana), Finetune (mesh test), Cross-repo |
| P2 / Semaine 2 | 12 | Finetune (DPO/SimPO, GRPO, validation), Infra (alerting, Langfuse) |
| P3+ / Semaine 3+ | 8 | Finetune (continuous cycle, dataset HF), Core (CoreML, ZeroClaw) |
| Conditionnel | 10 | Cockpit/Ops (extend only if needed), CAD (hors scope) |
| Backlog | 18 | Agent Zero (6), GPU benchmark, components review, candidates bench |
| Bloqué | 6 | AI Novel Engine runtime issues |
| Cross-repo | 9 | crazy_life, Kill_LIFE, llmfit |
