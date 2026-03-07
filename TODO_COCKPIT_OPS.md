# TODO - Cockpit / Ops / Observability

Etat de reference au 7 mars 2026.

## 1. Ce qui est deja livre

- [x] Cockpit React unifie avec shell, navigation, responsive et accessibilite clavier
- [x] Refonte des pages operations (`Dashboard`, `Metrics`, `Infrastructure`, `Logs`)
- [x] `agent-zero` visible comme lane lead dans le cockpit
- [x] Trace inter-agent native dans le core avec `run_id`
- [x] Lane `Logs` branchee sur les traces natives et les incidents services
- [x] Routes API de facade pour `summary`, `sources`, `logs/recent`, `agent-traces/*`
- [x] Scaffolding Docker pour `loki`, `promtail`, `otel-collector`

## 2. Blocage reel actuel

Le prochain lot n'est plus la refonte UI.
Le vrai travail restant est d'achever l'observability complementaire deja commencee localement:

- [ ] finaliser `ops-agent` pour les logs machine + Docker live
- [ ] finir `/api/ops/logs/query` pour l'historique Loki
- [ ] terminer le mode `history` de la page `Logs`
- [ ] brancher les exporteurs OTel reels dans le core et l'API

## 3. Priorite immediate

### Ops Agent
- [ ] valider `deploy/ops_agent/app.py`
- [ ] exposer `/health`, `/sources`, `/summary`, `/logs/recent`
- [ ] verifier collecte Docker via socket Unix
- [ ] verifier fallback propre quand `journald` n'est pas disponible

### Facade API ops
- [ ] finir le merge `ops-agent + traces natives + Loki` dans `api/src/routes/ops.ts`
- [ ] stabiliser `/api/ops/logs/recent`
- [ ] stabiliser `/api/ops/logs/query`
- [ ] garder auth obligatoire sur les routes ops

### Frontend Logs
- [ ] finir les filtres `mode/source/service/query/window`
- [ ] distinguer proprement `live` vs `history`
- [ ] garder les CTAs `agent-zero`
- [ ] verifier le rendu des sources `machine`, `service`, `agent-trace`

## 4. Priorite suivante

### OTel / Loki
- [ ] brancher l'export OTLP du core
- [ ] brancher l'export OTLP de l'API
- [ ] enrichir Promtail pour parser les logs JSON structures
- [ ] verifier les labels Loki utiles: `source`, `run_id`, `agent_name`, `event_type`, `severity`

### Historique cockpit
- [ ] requete historique Loki exploitable depuis `Logs`
- [ ] filtres persistants dans l'URL en mode history
- [ ] handling propre des erreurs Loki/timeout

## 5. Complement optionnel

- [ ] statut `AgentSight` dans `/api/ops/sources`
- [ ] lien/documentation d'usage AgentSight si installe
- [ ] aucune dependance critique du cockpit a AgentSight

## 6. Hors perimetre de ce lot

- [ ] tuning ClickHouse agressif
- [ ] TLS / certificat public
- [ ] lot CAD / KiCad local
- [ ] stabilisation batch fine-tuning end-to-end

## 7. Ordre recommande

1. Finir `ops-agent` et les routes API ops.
2. Finir le mode `history` de `Logs`.
3. Valider `core`, `api`, `web`, generation compose.
4. Brancher ensuite les exporteurs OTel et l'historique Loki.
5. Garder `AgentSight` en complement optionnel, en dernier.
