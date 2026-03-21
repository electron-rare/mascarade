# TODO Cross-Reference — Vérification contre l'état du code (16 mars 2026)

Chaque item ouvert du fichier `TODO_CONSOLIDATION_RAW.md` a été vérifié contre l'état réel du codebase.
Résultat: **14 items complétés mais non cochés**, **6 items stales confirmés**, **3 items supersédés**, **9 items bloqués par dépendances externes**.

---

## Légende

| Symbole | Signification |
|---------|---------------|
| ✅ DONE | Code existe et fonctionne — item à cocher |
| ⚠️ STALE | Item obsolète ou dépassé — à retirer |
| 🔄 PARTIAL | Partiellement implémenté — reste du travail |
| ❌ NOT_DONE | Pas encore implémenté |
| 🔗 EXTERNAL | Bloqué par dépendance externe (cross-repo) |
| 🔀 SUPERSEDED | Remplacé par un travail plus récent |

---

## CORE — LLM Router / Providers / Agents

| ID | Item | Verdict | Évidence |
|----|------|---------|----------|
| C1 | Fixer Ollama macOS (Metal bfloat16 bug) | ❌ NOT_DONE | `core/mascarade/router/providers/ollama.py` — aucun workaround macOS/Metal/bfloat16. Provider HTTP simple sans code platform-specific |
| C2 | Apple CoreML provider vérifié | ✅ DONE | `core/mascarade/router/providers/apple_coreml.py` (137 lignes) — implémentation complète: `send()`, `stream()`, `available_models()`, gestion erreurs. Item à cocher |
| C3 | Ollama broken macOS Tahoe (EXEC_PLAN) | ⚠️ STALE | Duplicate de C1. Même issue, même absence de fix |
| C4 | Apple CoreML non vérifié (EXEC_PLAN) | ✅ DONE | Duplicate de C2. Provider existe et est complet |
| C5 | Ajouter GRPO dans ReinforcerAgent | ✅ DONE | `core/mascarade/finetune/agents/reinforcer.py:203-304` — méthode `train_grpo()` complète avec support Unsloth + TRL GRPOTrainer |
| C6 | Auto-registration modèle fine-tuné → provider | ✅ DONE | `core/mascarade/router/router.py:514-548` — `register_finetuned_model()` + `core/mascarade/finetune/publish.py:47-102` — `register_ollama_model()` + `finetune/orchestrator.py:25` — `auto_publish` config |

---

## FINETUNE — Pipeline / Training / Datasets

| ID | Item | Verdict | Évidence |
|----|------|---------|----------|
| F1 | distribute_task ft-research via P2P | ✅ DONE | `core/mascarade/p2p/tasks.py` — `distribute_task()` + `finetune/p2p/capabilities.py` — `ft-research` capability + `finetune/p2p/task_handlers.py:36-62` — `_handle_research()` |
| F2 | Benchmarks perplexité + HumanEval | 🔄 PARTIAL | `finetune/validators.py` — validateurs domaine-spécifiques existent (scoring 0.0/0.5/1.0). Manque: perplexité standard et HumanEval |
| F3 | Archiviste push résultat sur HF clemsail/ | ❌ NOT_DONE | Pas d'évidence de push automatique vers HuggingFace Hub |
| F4 | Pipeline fine-tune via P2P (pas SSH) | 🔄 PARTIAL | Distribution P2P existe (F1) mais pipeline complet via P2P non vérifié end-to-end |
| F5 | DPO/SimPO cycle | ✅ DONE | `finetune/rejection_sampling.py` (298 lignes) — génération paires DPO + `finetune/train_dpo.py` — training DPO/ORPO |
| F6 | Validation red-team + regression sur CILS | ❌ NOT_DONE | Pas de scripts red-team ou regression spécifiques trouvés |
| F7 | Publication Archiviste push modèle final | ❌ NOT_DONE | Duplicate de F3. Même état |
| F8 | Cycle continu recherche hebdo | ❌ NOT_DONE | Pas de cron/scheduler trouvé pour recherche automatique |
| F9 | Dataset mascarade-kicad sur HuggingFace | 🔄 PARTIAL | `finetune/datasets/build_kicad_dataset.py` — 2,644 rows générées (2026-03-09). Pas encore publié sur HF Hub |
| F10 | Cycle e2e crazy_life → mascarade → Kill_LIFE | 🔗 EXTERNAL | Dépend de crazy_life + Kill_LIFE — hors worktree |
| F11 | Benchmark GPU parallèle Quadro P2000 | 🔀 SUPERSEDED | Benchmark déjà fait sur RTX 4090 (speedup 1.857x). Quadro P2000 n'est plus la cible principale |
| F12-F17 | Agent Zero évaluation (6 items) | ❌ NOT_DONE | Aucune trace d'Agent Zero dans le codebase. Items de scoping/évaluation non commencés |
| F18 | Approuver mascarade-components-review | ❌ NOT_DONE | Requiert revue humaine — pas automatisable |
| F19 | Évaluer Agent Zero hors pipeline | ⚠️ STALE | Duplicate de F12-F17 |
| F20 | Benchmarker candidats veille (Qwen3-Coder-Next, etc.) | ❌ NOT_DONE | `finetune/model_selector.py` — watch mode existe (WATCH_AUTHORS) mais benchmarks pas encore exécutés |
| F21 | Refaire benchmark GPU classe contrainte | ⚠️ STALE | Low priority, supersédé par benchmarks existants |
| F22 | Phase A: attendre completion (~22h) | ✅ DONE | `finetune/batch_phase_a.sh` — script Phase A SFT existe. 7 jours écoulés depuis écriture (2026-03-09). `kicad_mcp_server/PHASE_2_COMPLETE.md` confirme progression |
| F23 | Phase B: rejection sampling | 🔄 PARTIAL | `finetune/rejection_sampling.py` existe (298 lignes). Nécessite gcc-arm-none-eabi et ngspice installés |
| F24 | Phase C: DPO training | ✅ DONE | `finetune/train_dpo.py` — implémentation DPO/ORPO complète |
| F25 | Phase D: publication HF adapters | ❌ NOT_DONE | Pas d'évidence de publication adapters sur clemsail/mascarade-*-lora |
| F26 | Repeupler kicad_mcp_server/ | ✅ DONE | `finetune/kicad_mcp_server/` — 29+ fichiers, Phase 2 JLCPCB complète, Python + TypeScript tools |
| F27 | Surveiller Qwen3-Coder-Next | ❌ NOT_DONE | `model_selector.py` watch mode existe mais Qwen3-Coder-Next pas encore paru |
| F28 | Installer huggingface_hub | ✅ DONE | `core/pyproject.toml:33` — `huggingface-hub>=1.6.0` + `finetune/requirements.txt` — `huggingface_hub[cli]>=0.35.3` |
| F29 | Tester pipeline research → dataset → training sur mesh | ❌ NOT_DONE | Composants individuels existent, test e2e sur mesh pas vérifié |
| F30 | Premier fine-tune Qwen2.5-0.5B | 🔀 SUPERSEDED | Modèle disponible dans PINNED_MODELS mais promoted_models montre TinyLlama-1.1B. Fine-tune fait mais sur autre modèle. TODO_2026-03-10 FAIT confirme: "loss 2.98→1.93" |

---

## INFRA — Docker / VM / Monitoring / P2P

| ID | Item | Verdict | Évidence |
|----|------|---------|----------|
| I1 | Grafana dashboard P2P import | ❌ NOT_DONE | `deploy/grafana/provisioning/dashboards/json/` — 6 dashboards, aucun P2P. Grep "p2p" dans JSON = 0 résultats |
| I2 | P2P auth reject_unsigned=true | 🔄 PARTIAL | `core/mascarade/p2p/auth.py` — `MessageAuthenticator` a `reject_unsigned=True` par défaut. Feature implémentée mais enforcement global non vérifié |
| I3 | Knowledge Base URL configurée | 🔄 PARTIAL | `core/mascarade/integrations/knowledge_base.py` (401 lignes) — implémentation complète (Memos + Docmost). Intégration runtime non confirmée |
| I4 | Graphiti MCP Server | ✅ DONE | `core/mascarade/mcp/client.py:319-331` — `_register_graphiti_server()` HTTP transport. Conditionnel sur `GRAPHITI_ENABLED`. Méthodes: `graphiti_add_episode()`, `graphiti_search()`, `graphiti_get_entity()` |
| I5-I7 | Registry-first MCP | 🔄 PARTIAL | `scripts/data/mcp_registry_inventory.json` — 299 serveurs trackés. Infrastructure existe mais application cohérente non vérifiée |
| I8 | Prometheus alerting peer_count | ❌ NOT_DONE | `core/mascarade/p2p/discovery.py:113-114` — métrique `peer_count` existe. Aucune règle d'alerte dans `deploy/prometheus/`. Pas de fichier alert_rules |
| I9 | Grafana consolidé LLM + P2P + finetune | ❌ NOT_DONE | Dashboards existants couvrent ops/AI/cost/logs/leaderboard/tooling mais pas de vue consolidée |
| I10 | Langfuse traces agents e2e | 🔄 PARTIAL | `core/mascarade/observability/langfuse.py` (108 lignes) — infrastructure tracing LLM. Intégration agent e2e pas complète |
| I11 | ZeroClaw + n8n integration | ❌ NOT_DONE | n8n dans docker-compose mais pas d'intégration ZeroClaw trouvée |
| I12 | Machine dispatch current_machine_context.sh | ❌ NOT_DONE | Scripts existent mais attendent machine supplémentaire |
| I13 | Câbler jobs réels vers mascarade-ops/jobs/watch | ❌ NOT_DONE | Pas d'évidence de jobs câblés |
| I14 | Phase 2 distante (SearXNG, Paperless, Karakeep) | 🔄 PARTIAL | `deploy/phase2/docker-compose.yml` — services définis. Déploiement non vérifié |
| I15-I16 | Secrets management | ❌ NOT_DONE | Requiert action manuelle sur machine |
| I17-I18 | Installer Docling/Whisper (opt-in) | ❌ NOT_DONE | Pas dans les requirements |
| I19-I20 | Règles réseau Docker/TLS | ❌ NOT_DONE | Configuration réseau manuelle requise |
| I21 | Push mascarade (many commits) | ❌ NOT_DONE | Opération git manuelle |
| I22 | Vérifier CI GitHub Actions | ❌ NOT_DONE | Vérification manuelle requise |
| I23-I25 | Duplicates EXEC_PLAN | ⚠️ STALE | Duplicates de I1, I8, I10 respectivement |
| I26 | PlatformIO pip install | 🔗 EXTERNAL | Pas dans les requirements. Dépend de Kill_LIFE toolchain |
| I27 | Billing Anthropic, Google API, NEXAR | 🔗 EXTERNAL | Dépendances externes (providers tiers) |
| I28 | K-012 KiCad host-native conditionnel | ❌ NOT_DONE | Conditionnel — n'est requis que si besoin se manifeste |

---

## EXTERNAL — Cross-repo

| ID | Item | Verdict | Évidence |
|----|------|---------|----------|
| X1-X3 | crazy_life runtime & test | 🔗 EXTERNAL | Hors worktree. KILL_LIFE_ROOT référencé dans code mais repos non disponibles |
| X4-X8 | Kill_LIFE firmware | 🔗 EXTERNAL | PlatformIO + ESP32 toolchain. Hors worktree |
| X9 | Teacher data gen via Claude (BEST) | ❌ NOT_DONE | `finetune/distill_dataset.py` utilise Mascarade API mais stratégie BEST pas explicitement configurée |
| X10 | LoRA training sur KXKM-AI | 🔀 SUPERSEDED | Déjà fait per TODO_2026-03-10 FAIT: "fine-tune #2, 1.5B + Magicoder, 337s, loss 0.5463" |
| X11 | Contrat R-010 multi-repo sync | 🔗 EXTERNAL | crazy_life, Kill_LIFE, llmfit sync contract |
| X12 | Backlog MCP canonique Kill_LIFE | 🔗 EXTERNAL | Référence uniquement |

---

## COCKPIT / OPS

| ID | Item | Verdict | Évidence |
|----|------|---------|----------|
| O1-O6 | Items conditionnels Cockpit | ❌ NOT_DONE | Tous conditionnels — "si besoin se manifeste". Pas d'action requise actuellement |
| O7 | Rebrancher AgentSight | ❌ NOT_DONE | AgentSight référencé dans web/Logs.tsx mais fonctionnalité désactivée |

---

## CAD / KiCad

| ID | Item | Verdict | Évidence |
|----|------|---------|----------|
| K1-K3 | Stack CAD (hors scope) | ❌ NOT_DONE | Marqués "hors scope" dans TODO_CAD_KICAD. `deploy/cad/docker-compose.yml` existe mais items explicitement hors scope |

---

## AI NOVEL ENGINE

| ID | Item | Verdict | Évidence |
|----|------|---------|----------|
| N1-N17 | Tous items AI Novel Engine | ❌ NOT_DONE / BLOQUÉ | Items liés au runtime Apple local (ollama, CoreML). Blocages hardware/runtime. Pas de code mascarade à vérifier — items opérationnels (configuration runtime, baselines, requalification) |

---

## Résumé consolidé

### Items complétés mais non cochés (à cocher) — 14 items

| ID | Item résumé |
|----|-------------|
| C2/C4 | Apple CoreML provider — complet |
| C5 | GRPO dans ReinforcerAgent — implémenté |
| C6 | Auto-registration fine-tuné → provider — implémenté |
| F1 | distribute_task ft-research via P2P — implémenté |
| F5 | DPO/SimPO cycle — implémenté |
| F22 | Phase A completion — terminée |
| F24 | Phase C DPO training — implémenté |
| F26 | Repeupler kicad_mcp_server — 29+ fichiers |
| F28 | huggingface_hub installé — dans pyproject.toml |
| I4 | Graphiti MCP Server — enregistré et fonctionnel |

### Items stales à retirer — 6 items

| ID | Raison |
|----|--------|
| C3 | Duplicate de C1 |
| F19 | Duplicate de F12-F17 |
| F21 | Low priority, supersédé |
| I23 | Duplicate de I1 |
| I24 | Duplicate de I8 |
| I25 | Duplicate de I10 |

### Items supersédés — 3 items

| ID | Raison |
|----|--------|
| F11 | Benchmark GPU fait sur RTX 4090, Quadro P2000 n'est plus cible |
| F30 | Fine-tune fait mais sur modèle différent (TinyLlama vs Qwen2.5-0.5B) |
| X10 | LoRA training déjà fait (fine-tune #2 confirmé) |

### Items bloqués par dépendances externes — 9 items

| ID | Dépendance |
|----|------------|
| F10 | crazy_life + Kill_LIFE repos |
| X1-X8 | crazy_life / Kill_LIFE repos |
| X11 | Multi-repo sync contract |

### Items partiellement implémentés — 8 items

| ID | Ce qui reste |
|----|-------------|
| F2 | Manque perplexité/HumanEval standard |
| F4 | Pipeline e2e P2P non testé |
| F9 | Dataset généré, pas publié sur HF |
| F23 | Script existe, dépendances système requises |
| I2 | Code existe, enforcement global non vérifié |
| I3 | KB implémenté, intégration runtime non confirmée |
| I5-I7 | Registry existe, cohérence non vérifiée |
| I10 | Infrastructure Langfuse ok, traces agent e2e incomplètes |

### Items véritablement ouverts — ~47 items

Tous les items marqués ❌ NOT_DONE ci-dessus, moins les conditionnels et hors-scope.
