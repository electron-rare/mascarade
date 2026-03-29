# SPEC — Déploiement VM et Système d'Orchestration (Mascarade)

## 1. Objectif
Définir une architecture et un plan d'implémentation unifiés pour exploiter `mascarade` sur une VM dédiée, avec:
- un déploiement reproductible,
- un routage LLM résilient,
- une observabilité exploitable,
- un cadre d'exploitation sécurisé.

Cette spec sert de référence globale pour la machine hôte, la VM d'exécution, Docker, et les services applicatifs (`core` + `api`).

## 2. Périmètre
Inclus:
- architecture logique et runtime,
- conventions de déploiement (build, release, rollback),
- sécurité d'accès,
- monitoring/ops,
- roadmap d'implémentation.

Exclus:
- provisionnement cloud IaC complet (Terraform/Bicep),
- orchestration Kubernetes,
- HA multi-région.

## 3. État actuel (constaté)
- Monorepo avec:
  - `core/` (FastAPI + orchestration agents + router LLM)
  - `api/` (Hono gateway)
- Déploiement Docker Compose via [docker-compose.yml](docker-compose.yml)
- Auth Bearer supportée via `MASCARADE_API_KEY`
- Fonctions de résilience/observabilité déjà intégrées:
  - fallback provider,
  - cache mémoire,
  - métriques runtime,
  - load balancing provider,
  - endpoints de stats/reset.

## 4. Architecture cible (global machine + VM)

### 4.1 Topologie
- Machine de dev (locale):
  - édition code,
  - build/test local,
  - pilotage Docker vers VM via `docker context`.
- VM (runtime):
  - exécution des conteneurs `mascarade-core` et `mascarade-api`,
  - stockage volume persistant (`core-data`) pour données runtime (agents dynamiques),
  - exposition réseau des ports applicatifs.

### 4.2 Services
- `core` (port 8100):
  - endpoints métier + monitoring,
  - orchestration multi-agents,
  - router LLM (strategies: `best`, `cheapest`, `fastest`, `specific`),
  - fallback + cache + metrics + load-balancer.
- `api` (port 3100):
  - gateway HTTP,
  - auth middleware,
  - proxy des endpoints `core`.

### 4.3 Données
- Volume Docker `core-data`:
  - persistance de `data/agents.json` (agents dynamiques),
  - pas de dépendance DB externe à ce stade.

## 5. Exigences fonctionnelles
1. Déploiement en une commande (`docker compose up -d`) sur VM.
2. Résilience aux erreurs provider via fallback automatique.
3. Réduction coûts via cache de réponses.
4. Monitoring live:
   - métriques providers,
   - stats cache,
   - stats load balancing,
   - stats fallback.
5. Sécurité:
   - toutes routes sensibles protégées par Bearer token.

## 6. Exigences non fonctionnelles
- Disponibilité service: redémarrage auto (`restart: unless-stopped`).
- Observabilité minimale: endpoints JSON + logs conteneurs.
- Reproductibilité build: images Docker versionnées (tag Git recommandé).
- Sécurité secrets: variables injectées via `.env` VM, jamais commitées.
- Simplicité ops: rollback possible par retag image + recreate compose.

## 7. Contrat d'authentification
- Variable: `MASCARADE_API_KEY` (VM et API gateway).
- Header obligatoire (routes protégées):
  - `Authorization: Bearer <MASCARADE_API_KEY>`
- Route publique conservée:
  - `GET /health`

## 8. Contrat des endpoints d'exploitation

### 8.1 Core (protégés)
- `GET /metrics`
- `GET /metrics/{provider}`
- `POST /metrics/reset`
- `GET /cache/stats`
- `POST /cache/reset`
- `GET /load-balancer/stats`
- `POST /load-balancer/reset`
- `GET /fallback/stats`
- `POST /fallback/reset`

### 8.2 Gateway API
Préfixe `/api/agents/*`, proxy du contrat ci-dessus.

## 9. Processus de déploiement (VM)

### 9.1 Pré-requis VM
- Docker + Compose plugin installés.
- Fichier `.env` présent à la racine projet.
- Ports ouverts:
  - `3100/tcp` (gateway)
  - `8100/tcp` (optionnel si accès direct core requis)

### 9.2 Release standard
1. Build images:
   - `docker compose build`
2. Déploiement:
   - `docker compose up -d --force-recreate`
3. Smoke checks:
   - `GET /health` core,
   - `GET /health` api,
   - `GET /api/agents/metrics`.

### 9.3 Rollback
- Revenir au tag image précédent.
- `docker compose up -d --force-recreate`.

## 10. Stratégie d'observabilité
- Sources:
  - `docker compose logs -f core api`
  - endpoints de stats.
- KPIs minimum:
  - `total_requests`, `total_cost`, `error_rate` par provider,
  - `cache hit_rate`,
  - `fallback total_failures`,
  - `load balancing in-flight/pending`.

## 11. Sécurité et conformité minimale
- Secrets uniquement dans `.env` VM.
- Rotation périodique `MASCARADE_API_KEY` et clés provider.
- Pas d'exposition publique de `/metrics/*` sans auth.
- Journaliser les échecs auth (gateway + core).

## 12. Plan d'implémentation (phases)

### Phase A — Stabilisation runtime (immédiat)
- Vérifier cohérence modules `cache/metrics/load_balancer/fallback`.
- Ajouter tests unitaires dédiés résilience + cache + métriques.
- Geler contrat d'API monitoring.

### Phase B — Industrialisation déploiement
- Ajouter script release (`scripts/release.sh`): build + up + smoke.
- Tag d'image avec SHA commit.
- Ajouter check santé post-déploiement automatisé.

### Phase C — Ops avancée
- Dashboard externe (Grafana/Prometheus ou export JSON périodique).
- Politique de rétention logs.
- Alertes minimales (core down, error_rate provider élevée).

## 13. Critères d'acceptation
1. Déploiement complet VM en < 5 min sans intervention manuelle hors `.env`.
2. `GET /health` core + api retournent `status=ok`.
3. Endpoints monitoring répondent via gateway auth.
4. Un échec provider est visible dans `fallback.stats`.
5. Un second appel identique augmente le `cache hit_count`.

## 14. Risques principaux
- Incohérence entre code local et image déployée (cache build stale).
- Dérive de config `.env` entre dev et VM.
- Fallback insuffisant si aucun provider valide.
- Cache mémoire non partagé si scale horizontal futur.

## 15. Décisions techniques
- Docker Compose conservé comme orchestrateur runtime (v1 du système).
- Auth Bearer simple conservée pour limiter la complexité opérationnelle.
- Monitoring basé endpoints JSON (pas de stack observabilité lourde obligatoire en v1).

---
Version: `v1.0`
Repo: racine du repository (`.`)
