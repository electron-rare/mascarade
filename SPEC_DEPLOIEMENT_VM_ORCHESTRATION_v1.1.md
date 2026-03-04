# SPEC v1.1 — Déploiement VM et Orchestration (Exécutable)

## 1. But
Transformer la vision v1.0 en plan d'exécution concret pour opérer `mascarade` sur VM avec déploiement fiable, résilience LLM, monitoring exploitable, et sécurité minimale.

## 2. Cible opérationnelle
- Runtime unique sur VM via Docker Compose.
- Gateway `api` en frontal, `core` en service privé.
- Auth Bearer active sur routes protégées.
- Observabilité via endpoints runtime + logs conteneurs.

## 3. Backlog d'implémentation

## P0 (bloquant prod)

### P0-01 — Stabiliser cohérence modules résilience
- Scope: aligner interfaces `router` <-> `cache/metrics/load_balancer/fallback`.
- Livrables:
  - appels méthodes uniformisés,
  - erreurs runtime supprimées au boot,
  - tests unitaires verts.
- DoD:
  - `python -m py_compile` passe,
  - `pytest -q` passe,
  - `docker compose up -d` sans crash restart loop.

### P0-02 — Auth bout-en-bout gateway -> core
- Scope: propagation `Authorization: Bearer` de `api` vers `core`.
- Livrables:
  - middleware auth API,
  - dépendance auth core,
  - config `.env` documentée (`MASCARADE_API_KEY`).
- DoD:
  - sans token: endpoints protégés retournent `401`,
  - avec token: `GET /api/agents/metrics` retourne `200`.

### P0-03 — Déploiement déterministe VM
- Scope: process unique de release + smoke.
- Livrables:
  - script `scripts/release_vm.sh` (build, up, smoke, exit code strict),
  - script `scripts/smoke_vm.sh` (health + endpoints clés).
- DoD:
  - exécution script en une commande,
  - rollback documenté et testé.

## P1 (important exploitation)

### P1-01 — Monitoring runtime standardisé
- Scope: figer contrat JSON des endpoints:
  - `/metrics`, `/cache/stats`, `/load-balancer/stats`, `/fallback/stats`.
- Livrables:
  - schémas de réponse stables,
  - champs obligatoires documentés.
- DoD:
  - docs + exemples `curl` à jour,
  - test d'intégration des endpoints.

### P1-02 — Persistance agents dynamiques
- Scope: fiabiliser `AgentRegistry` (load/save, builtins non persistés).
- Livrables:
  - stratégie de persistance unique (`data/agents.json`),
  - tests de non-régression.
- DoD:
  - redémarrage conteneur conserve agents dynamiques,
  - builtins restent non dupliqués/non persistés.

### P1-03 — Gestion secrets et config VM
- Scope: hardening config runtime.
- Livrables:
  - `.env.example` complet et cohérent,
  - checklist de rotation clés,
  - validation des placeholders rejetés.
- DoD:
  - démarrage avec placeholders -> providers vides,
  - démarrage avec vraies clés -> providers visibles.

## P2 (amélioration continue)

### P2-01 — Tagging image + release metadata
- Scope: tag images par commit SHA/date.
- Livrables:
  - convention de tag,
  - endpoint/version exposant commit courant.
- DoD:
  - image traçable de bout en bout.

### P2-02 — Alerting minimal
- Scope: alertes basiques sur disponibilité et dérive erreurs.
- Livrables:
  - règles: core down, 5xx API, fallback failures élevés.
- DoD:
  - test d'alerte simulée validé.

### P2-03 — Politique de maintenance Docker VM
- Scope: nettoyage périodique (images/cache/volumes orphelins).
- Livrables:
  - tâche cron/systemd timer,
  - commande de clean documentée.
- DoD:
  - runbook ops validé.

## 4. Plan de sprint recommandé

### Sprint 1 (P0)
1. P0-01
2. P0-02
3. P0-03

### Sprint 2 (P1)
1. P1-01
2. P1-02
3. P1-03

### Sprint 3 (P2)
1. P2-01
2. P2-02
3. P2-03

## 5. Commandes de validation standard

```bash
# Python
cd core
pytest -q

# TypeScript
cd ../api
npm run build

# Runtime
cd ..
docker compose build
docker compose up -d
curl -f http://localhost:8100/health
curl -f http://localhost:3100/health
```

## 6. Critères de sortie (go-live VM)
- Tous tickets P0 fermés.
- Smoke runtime vert 3 runs consécutifs.
- Auth validée sur routes protégées.
- Monitoring endpoint stable et documenté.
- Runbook de déploiement + rollback validé.

---
Version: `v1.1`
Date: `2026-03-03`
Repo: `/Users/cils/mascarade`
