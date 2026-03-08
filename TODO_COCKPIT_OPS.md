# TODO - Cockpit / Ops / Observability

Etat de reference au 7 mars 2026.
Mis a jour apres audit croise code/docs le 7 mars 2026.
Recale sur le runtime reel le 8 mars 2026.

## 1. Ce qui est deja livre

- [x] Cockpit React unifie avec shell, navigation, responsive et accessibilite clavier
- [x] Refonte des pages operations (`Dashboard`, `Metrics`, `Infrastructure`, `Logs`)
- [x] `agent-zero` visible comme lane lead dans le cockpit
- [x] Trace inter-agent native dans le core avec `run_id`
- [x] Lane `Logs` branchee sur les traces natives et les incidents services
- [x] Routes API de facade pour `summary`, `sources`, `logs/recent`, `agent-traces/*`
- [x] Scaffolding Docker pour `loki`, `promtail`, `otel-collector`

## 2. Implemente depuis le dernier TODO (verifie par audit)

### Ops Agent (`deploy/ops_agent/app.py`)
- [x] `ops-agent` finalise: /health, /sources, /summary, /logs/recent, /logs/stream (SSE)
- [x] Collecte Docker via socket Unix `/var/run/docker.sock`
- [x] Fallback propre quand `journald` n'est pas disponible
- [x] Inference de severite via regex, parsing de logs structures

### Facade API ops (`api/src/routes/ops.ts`)
- [x] Merge `ops-agent + traces natives + Loki` termine
- [x] `/api/ops/logs/recent` stable (merge traces + probes + ops-agent + docker events)
- [x] `/api/ops/logs/query` implemente: query_range Loki, filtres source/q/run_id/agent_name/severity/since/service
- [x] `/api/ops/logs/stream` proxy SSE vers ops-agent
- [x] Auth obligatoire sur toutes les routes /api/* (middleware timing-safe)
- [x] MCP probe synthetique (`probeMcpRuntime()`) avec cache TTL dans `/summary`

### Frontend Logs (`web/src/pages/Logs.tsx`)
- [x] Toggle `live` (SSE streams) vs `history` (requete Loki)
- [x] Filtres: source, severity, run_id, agent_name, event_type, service, routing_role/provider/model
- [x] Recherche texte en mode history (parametre `q` vers Loki)
- [x] Fenetres temporelles history: 15m, 1h, 6h, 24h
- [x] CTAs `agent-zero` conserves
- [x] Panneau detail run avec timeline evenements
- [x] Posture sources affichee

### Exporteurs OTel
- [x] Export OTLP custom dans le core (`core/mascarade/observability/otel.py`): schedule_otlp_log(), OTEL_ENABLED
- [x] Export OTLP custom dans l'API (`api/src/lib/otel.ts`): emitStructuredLog(), fire-and-forget
- [x] Mapping severite OTLP: debug(5), info(9), warning(13), error(17), critical(21)
- [x] Appele depuis agent_trace.py (core) et agents.ts (API)

### OTel / Loki / Prometheus / Grafana (verifie en live)
- [x] OTel Collector ecoute reellement sur `0.0.0.0:4317`, `0.0.0.0:4318` et `/health` sur `0.0.0.0:13133`
- [x] Logs OTLP routes vers Loki via `deploy/otel-collector/config.yaml`
- [x] Smoke OTLP -> Loki valide avec labels `source`, `run_id`, `agent_name`, `event_type`, `mode`, `provider`, `routing_role`, `routing_provider`
- [x] Telemetrie interne du collector exposee sur `:8888` et scrapee par Prometheus
- [x] `ops-agent` expose `/metrics` pour Prometheus
- [x] Grafana datasources provisionnees en code (`Loki`, `Prometheus`) et chargees au demarrage
- [x] Dashboard Grafana provisionne en code: `Mascarade Ops Overview`
- [x] Dashboard Grafana provisionne en code: `Mascarade Service Logs`
- [x] Smoke OTLP versionne: `scripts/smoke_otel_loki.sh`

### Promtail
- [x] Parsing JSON structure enrichi: `severity`, `source`, `run_id`, `agent_name`, `event_type`, `mode`, `provider`, `model`, `routing_role`, `routing_provider`, `routing_model`
- [x] Report versionne de cardinalite Loki: `scripts/loki_cardinality_report.sh`

### Frontend Logs (verifie dans le code)
- [x] Filtres history persistants dans l'URL
- [x] Handling de base des erreurs Loki/timeout avec notices explicites

## 3. Ce qui reste reellement

### OTel Collector
- [ ] Sortir `traces` et `metrics` du mode `debug` vers un backend reel si l'on veut les conserver
- [ ] Decider si le warning de securite `0.0.0.0` doit etre accepte tel quel (bind hote deja borne en `127.0.0.1`) ou davantage restreint

### Grafana
- [ ] Etendre encore au-dela des dashboards de base deja poses (`Ops Overview`, `Service Logs`) si un domaine le justifie

### Promtail
- [ ] Verifier sur trafic reel la cardinalite des labels enrichis (`run_id`, `provider`, `routing_*`) a l'aide de `scripts/loki_cardinality_report.sh`
- [ ] Ajuster la matrice `labels` vs `structured metadata` si Loki commence a grossir trop vite

### Frontend Logs (ajustements mineurs)
- [ ] Rien de bloquant dans ce lot; garder seulement les retours UX a froid apres usage

## 4. Complement optionnel

- [ ] Statut `AgentSight` dans `/api/ops/sources`
- [ ] Lien/documentation d'usage AgentSight si installe

## 5. Hors perimetre de ce lot

- [ ] Tuning ClickHouse agressif
- [ ] TLS / certificat public
- [ ] Lot CAD / KiCad local
- [ ] Stabilisation batch fine-tuning end-to-end

## 6. Ordre recommande

1. Configurer le vrai exporter OTel Collector (remplacer le stub debug).
2. Verifier la cardinalite Loki sur trafic reel et ajuster si besoin.
3. Garder `AgentSight` en complement optionnel, en dernier.
