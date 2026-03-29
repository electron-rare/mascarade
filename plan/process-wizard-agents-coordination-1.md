# Plan — Wizard Agents Coordination
## process-wizard-agents-coordination-1

**Créé**: 2026-03-29
**Stack**: `core/` Python (FastAPI)
**Scope**: `core/mascarade/agents/coordination.py` + endpoints API + tests + CI

---

## Contexte

Le système d'agents Mascarade (242 définis, 9 en prod) n'a pas de mécanisme de coordination
structuré entre agents. Un "wizard" de coordination doit permettre :

1. De sélectionner les agents utiles pour une tâche complexe (agent matrix).
2. De les orchestrer en séquence ou en parallèle via le moteur existant.
3. D'exposer un endpoint de coordination haut niveau.
4. De valider la chaîne sur les 5 machines du mesh P2P.

---

## Phases et tâches

### Phase 1 — Spec & contrat (TASK-001 à TASK-004)

| ID | Tâche | Livrable | Statut |
|----|-------|----------|--------|
| TASK-001 | Rédiger doc spec `docs/agents/COORDINATION_SPEC.md` | MD spec formelle | À faire |
| TASK-002 | Définir le schéma Pydantic CoordinationRequest/CoordinationResult | agents/schemas.py étendu | À faire |
| TASK-003 | Dresser la matrice agents x domaines (9 prod + extensions) | Section COORDINATION_SPEC.md | À faire |
| TASK-004 | Définir les règles de sélection automatique (domaine -> agents) | agents/selector.py | À faire |

**Critère d'acceptation Phase 1** : mypy mascarade/agents/ sans erreur, schémas valides Pydantic v2.

---

### Phase 2 — Moteur de coordination (TASK-005 à TASK-010)

| ID | Tâche | Livrable | Statut |
|----|-------|----------|--------|
| TASK-005 | Créer core/mascarade/agents/coordination.py | Module CoordinationEngine | À faire |
| TASK-006 | Implémenter select_agents(request) — règles domaine+compétences | Méthode + tests unitaires | À faire |
| TASK-007 | Implémenter run_sequential(agents, context) — pipeline séquentiel | Méthode async + tests | À faire |
| TASK-008 | Implémenter run_parallel(agents, context) — gather avec timeout | Méthode async + tests | À faire |
| TASK-009 | Intégrer avec orchestrator/engine.py (délégation si plan complexe) | Adapter dans engine.py | À faire |
20
20
| TASK-010 | 20+ tests unitaires tests/test_agents_coordination.py | Suite de tests >= 20 tests | À faire |

**Critère d'acceptation Phase 2** : python -m pytest tests/test_agents_coordination.py -> 100% pass.

---

### Phase 3 — Endpoints API (TASK-011 à TASK-015)

| ID | Tâche | Livrable | Statut |
|----|-------|----------|--------|
| TASK-011 | Créer core/mascarade/routers/coordination.py | Router FastAPI /api/coordination | Fait (2026-03-29) |
| TASK-012 | POST /api/coordination/run — lance une coordination | Endpoint + validation 422/503 | Fait (2026-03-29) |
| TASK-013 | GET /api/coordination/status/{task_id} — polling résultat | Endpoint + store en mémoire | Fait (2026-03-29) |
| TASK-014 | GET /api/coordination/agents — liste agents disponibles | Endpoint + filtres query params | Fait (2026-03-29) |
| TASK-015 | Tests HTTP tests/test_routers_coordination.py (>= 16 tests) | Tests httpx.ASGITransport | Fait (2026-03-29, 16 tests) |

**Critère d'acceptation Phase 3** : ruff check clean + 16+ tests HTTP pass.

---

### Phase 4 — CLI & installation (TASK-016 à TASK-018)

| ID | Tâche | Livrable | Statut |
|----|-------|----------|--------|
| TASK-016 | Commande CLI mascarade coordination run <domain> <task> | core/mascarade/cli/coordination.py | À faire |
| TASK-017 | Enregistrer le router dans core/mascarade/server.py | Patch server.py | Fait (2026-03-29) |
| TASK-018 | Mise à jour docs/API.md — section Coordination | Section docs + exemples curl | À faire |

---

### Phase 5 — CI/CD (TASK-019 à TASK-022)

| ID | Tâche | Livrable | Statut |
|----|-------|----------|--------|
| TASK-019 | Ajouter coordination dans le filtre changes de ci.yml | Patch .github/workflows/ci.yml | À faire |
| TASK-020 | Vérifier que core job couvre test_agents_coordination.py | Validation CI | À faire |
| TASK-021 | Ajouter job coordination_integration (smoke test end-to-end) | Job YAML ci.yml | À faire |
| TASK-022 | Matrix CI : ubuntu-latest + commentaire macos (auto) | Matrix ci.yml | À faire |

---

### Phase 6 — Validation 5 machines (TASK-023 à TASK-026)

| ID | Tâche | Livrable | Statut |
|----|-------|----------|--------|
| TASK-023 | Smoke test GrosMac local : curl POST /api/coordination/run | Log de validation | À faire |
| TASK-024 | Smoke test Tower : même endpoint via réseau LAN | Log de validation | À faire |
| TASK-025 | Smoke test KXKM-AI : coordination avec agent GPU-heavy | Log de validation | À faire |
| TASK-026 | Vérifier mesh P2P : coordination distribuée distribute_task | Résultat distribute_task | À faire |

---

## Architecture cible

```raw
POST /api/coordination/run
    |
    v
CoordinationEngine.select_agents(domain, task)
    |  Uses: AgentRegistry, skills matrix, domain rules
    v
CoordinationEngine.run_sequential|parallel(agents, context)
    |  Delegates to: orchestrator/engine.py for complex plans
    v
CoordinationResult(task_id, results[], duration_ms, agents_used[])
```

## Contraintes

- Async-first : toutes les méthodes I/O sont async def.
- Pas de modèle local chargé : coordination via agents distants.
- Pydantic v2 pour tous les schémas.
- Tests sans @pytest.mark.asyncio (asyncio_mode = auto dans pyproject.toml).
- Patch target : si import local dans router, patcher le module source.

## Démarrage recommandé

```bash
cd core
python -m pytest tests/test_agents_coordination.py -v
python -m pytest tests/test_routers_coordination.py -v
ruff check mascarade/agents/ mascarade/routers/coordination.py
mypy mascarade/agents/coordination.py
```
