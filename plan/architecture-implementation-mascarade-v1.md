# Plan Architecture — Implémentation Mascarade v1
## architecture-implementation-mascarade-v1

**Créé**: 2026-03-29
**Scope**: Architecture cible complète — Router -> Agents -> Orchestrateur -> RAG -> P2P -> MCP
**Référence**: docs/ARCHITECTURE.md

---

## Objectif

Ce document fixe l'architecture d'implémentation cible de Mascarade v1 :
quels composants existent, lesquels sont à consolider, et dans quel ordre.

---

## État des composants (audit 2026-03-29)

| Composant | Module | État | Priorité |
|-----------|--------|------|----------|
| Router LLM | router/ | Prod (34 providers) | Maintenance |
| Agents registry | agents/ | 9 prod, 242 définis | Coordination à faire |
| Orchestrateur | orchestrator/ | sequential/parallel/DAG | Stable |
| RAG pipeline | rag/ | BGE-M3 -> Qdrant -> rerank | Tests I3 |
| Node Engine | node_engine/ | DAG typé | Stable |
| MCP server | mcp/ | Registry-first | Décisions I3 |
| P2P mesh | p2p/ | 5 noeuds | distribute_task à valider |
| Coordination agents | agents/coordination.py + routers/coordination.py | Implémenté (Phase 2+3) | Next: Phase 4/5 |
| KB handler | integrations/kb_handler.py | Renforcé I3 | OK |
| Fine-tune pipeline | finetune/ | SFT + SimPO + GGUF | Publication HF |
| OpenBuro | api/src/routes/openburo.ts | Phase 1 done | Stable |
| Graphiti MCP | VM externe | ABSENT | Backlog infra |

---

## Séquence d'implémentation recommandée

### Tranche A — Coordination agents

Voir plan/process-wizard-agents-coordination-1.md pour le détail TASK-001 à TASK-026.

Livrables :
- core/mascarade/agents/coordination.py
- core/mascarade/routers/coordination.py
- GET /api/coordination/agents, POST /api/coordination/run, GET /api/coordination/status/{id}
- 36+ tests (20 unitaires + 16 HTTP)

### Tranche B — P2P distribute_task validation

Blockers :
- distribute_task action finetune -> implémentée, non testée end-to-end vers GrosMac.

Livrables :
- Test E2E distribute_task ft-research -> GrosMac -> résultats HF
- Log de validation dans docs/audit/

### Tranche C — Monitoring consolidé

Items ouverts :
- Grafana P2P dashboard import (grafana-dashboard.json existe, import pas automatisé)
- Prometheus alerting peer_count < expected
- Grafana consolidé LLM + P2P + finetune metrics

Livrables :
- scripts/import_grafana_dashboard.sh
- core/monitoring/alerts.yml (règles Prometheus)

### Tranche D — Graphiti MCP VM

Prérequis :
- VM Tower disponible avec port 7474 libre (Neo4j).
- Config ~/.codex/config.toml mise à jour hors sandbox.

Livrables :
- Graphiti MCP Server déployé sur Tower.
- Intégration dans le registre MCP mascarade.

---

## Conventions transverses

- Async-first : toute I/O dans core/ est async def.
- Pydantic v2 : tous les schémas sont des BaseModel ou RootModel.
- Tests sans @pytest.mark.asyncio : asyncio_mode = auto dans pyproject.toml.
- Patch target : imports locaux dans un router -> patcher le module source.
- Ruff + black : ruff check --fix après chaque modification.
- Coverage : --cov-fail-under=50 en CI (cible 60% fin Q3).

---

## Références

- docs/ARCHITECTURE.md
- docs/API.md
- plan/process-wizard-agents-coordination-1.md
- docs/TODO_2026-03-10.md
- docs/audit/MCP_REGISTRY_FIRST_2026-03-14.md
