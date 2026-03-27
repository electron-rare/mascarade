# Open Buro — Alignment Analysis

> Standard d'interopérabilité EU pour suites collaboratives souveraines
> https://openburo.eu/

## Score global : ~40%

## Mapping standards → infrastructure existante

| # | Standard Open Buro | Composant existant | Couverture | Gap |
|---|---|---|---|---|
| 1 | **SSO unifié (OIDC)** | Keycloak `auth.saillant.cc` (realm zacus, 15+ clients) | **85%** | Manque FranceConnect (JAR installé, pas configuré) |
| 2 | **Format d'app standard** | Aucun | **25%** | Pas de manifest, pas de packaging standard |
| 3 | **Registre d'apps** | Aucun (inventaire manuel) | **20%** | Besoin d'un registry dynamique |
| 4 | **API settings commune** | Aucun | **10%** | Chaque app a ses propres env vars |
| 5 | **Event streaming** | Webhooks N8N, WebSocket mascarade | **20%** | Pas de bus CloudEvents standardisé |
| 6 | **Business objects** | Chaque app a son schéma | **15%** | Pas de définitions partagées contact/doc/tâche |
| 7 | **Knowledge graph sémantique** | Neo4j + Graphiti | **70%** | Besoin d'ingestion automatique depuis les apps |
| 8 | **API RAG/Search unifiée** | Qdrant + SearXNG + mascarade RAG pipeline | **75%** | Manque indexation docs Suite Numérique |
| 9 | **Workspaces cross-apps** | Aucun | **10%** | Les apps fonctionnent en silos |
| 10 | **Centre de notifications** | ntfy | **45%** | Intégration partielle, pas de centre unifié |

## Points forts

- **SSO/OIDC** : Keycloak couvre tous les services, forward-auth + OIDC natif (Grist)
- **IA/RAG** : mascarade-core avec 25+ providers LLM, Qdrant, pipeline RAG complet
- **Knowledge graph** : Neo4j + Graphiti déjà opérationnels sur tower
- **Observabilité** : Prometheus + Grafana + Loki + Tempo (85%)

## Gaps prioritaires (P1) — effort ~60h

### 1. App Manifest + Registry
Créer un format JSON standard pour déclarer chaque app :
```json
{
  "id": "dolibarr",
  "name": "Dolibarr ERP",
  "url": "https://erp.saillant.cc",
  "icon": "/assets/dolibarr.svg",
  "auth": { "type": "oidc", "client_id": "dolibarr" },
  "capabilities": ["contacts", "invoices", "projects"],
  "events": { "publish": ["contact.created", "invoice.sent"], "subscribe": ["contact.updated"] },
  "api": { "openapi": "https://erp.saillant.cc/api/openapi.json" }
}
```
**Endpoint** : `GET /openburo/apps` — liste toutes les apps enregistrées.

### 2. Event Bus (CloudEvents)
Utiliser **Redis Streams** (déjà déployé) comme bus d'événements :
- Format : CloudEvents v1.0 (JSON)
- Chaque app publie ses événements sur un stream Redis
- mascarade-core consomme et route les événements
- **Endpoints** : `POST /openburo/events`, `GET /openburo/events/stream` (SSE)

### 3. Business Objects
Définir des schémas partagés (JSON Schema) :
- `Contact` : id, name, email, phone, org, source_app
- `Document` : id, title, url, mime_type, created_by, source_app
- `Task` : id, title, status, assignee, due_date, source_app
- `Invoice` : id, number, amount, currency, status, client, source_app

**Endpoints** : `GET /openburo/objects/{type}` — recherche unifiée cross-apps.

## Gaps importants (P2) — effort ~45h

### 4. Workspaces cross-apps
Un "workspace" = un projet qui agrège des ressources de plusieurs apps :
```json
{
  "id": "projet-client-x",
  "name": "Client X — Carte PCB",
  "apps": {
    "docs": { "folder_id": "abc123" },
    "grist": { "doc_id": "def456" },
    "dolibarr": { "project_id": 42 },
    "calendars": { "calendar_id": "ghi789" }
  }
}
```
**Endpoint** : `GET /openburo/workspaces/{id}` — vue unifiée d'un projet.

### 5. Notifications unifiées
Agréger les notifications de toutes les apps dans ntfy :
- Chaque app pousse vers `POST /openburo/notifications`
- mascarade route vers ntfy avec catégorisation
- er-ops affiche un centre de notifications unifié

### 6. API Settings
Config centralisée dans PostgreSQL :
- `GET /openburo/settings/{app_id}` — lire la config d'une app
- `PUT /openburo/settings/{app_id}` — modifier
- Propagation en temps réel via event bus

## Gaps P3 — effort ~30h

### 7. Search unifiée
Étendre le RAG pipeline pour indexer les documents de la Suite Numérique :
- Docs/Impress → extraction texte → embedding → Qdrant
- Grist → export CSV → embedding
- Dolibarr → contacts/factures → embedding
- **Endpoint** : `GET /openburo/search?q=...` — recherche cross-apps

### 8. Sécurité E2E
- Vault pour les secrets partagés (Keycloak + apps)
- Chiffrement des business objects en transit

## Plan d'action (3 phases, 5-8 semaines)

### Phase 1 — Fondations (2 semaines)
- [ ] App Manifest JSON + endpoint `/openburo/apps`
- [ ] Event bus Redis Streams + CloudEvents format
- [ ] Business Objects schemas (Contact, Document, Task, Invoice)

### Phase 2 — Intégration (2-3 semaines)
- [ ] Connecteurs Dolibarr → event bus (contact.created, invoice.sent)
- [ ] Connecteur Grist → event bus (row.created, row.updated)
- [ ] Workspaces cross-apps (endpoint + stockage PostgreSQL)
- [ ] Notifications unifiées → ntfy

### Phase 3 — Intelligence (1-3 semaines)
- [ ] Search unifiée (indexation Suite Numérique → Qdrant)
- [ ] Knowledge graph auto-alimenté (Neo4j ← event bus)
- [ ] er-ops comme client Open Buro (SDK unifié)

## Endpoints API à créer dans mascarade-api (Hono)

```
/openburo/apps                    GET     — liste des apps enregistrées
/openburo/apps/{id}               GET     — détail d'une app
/openburo/events                  POST    — publier un événement CloudEvents
/openburo/events/stream           GET     — SSE stream d'événements
/openburo/objects/{type}          GET     — recherche business objects cross-apps
/openburo/objects/{type}/{id}     GET     — détail d'un objet
/openburo/workspaces              GET     — liste des workspaces
/openburo/workspaces/{id}         GET     — détail workspace (ressources cross-apps)
/openburo/workspaces              POST    — créer un workspace
/openburo/notifications           POST    — envoyer une notification
/openburo/notifications           GET     — liste notifications (filtrable)
/openburo/search                  GET     — recherche unifiée cross-apps
/openburo/settings/{app_id}       GET     — config d'une app
/openburo/settings/{app_id}       PUT     — modifier config
```

## Sources
- [Open Buro](https://openburo.eu/)
- [FOSDEM 2026 — Open Buro talk](https://fosdem.org/2026/schedule/event/GMKDKW-foss-vs-office-365/)
- [GoodTech — OpenBuro](https://goodtech.info/openburo-standard-europeen-orchestration-alternative-microsoft-365-dinum-linagora/)

---
*Généré le 2026-03-27 — Alignement mascarade × Open Buro*
