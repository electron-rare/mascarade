# TODO - Cockpit / Ops / Observability

Etat de reference recale au 8 mars 2026.
Le lot local est stable; ce fichier ne porte plus de blocage critique.

## 1. Ce qui est livre et verifie

- [x] Cockpit React unifie (`Dashboard`, `Metrics`, `Infrastructure`, `Logs`, `OpsHub`, `Orchestrate`)
- [x] `ops-agent` finalise: `/health`, `/sources`, `/summary`, `/logs/recent`, `/logs/stream`
- [x] Facade API ops complete: merge `ops-agent + traces natives + Loki + probes MCP`
- [x] Auth obligatoire sur les routes `/api/*`
- [x] Logs frontend en mode `live` et `history`, avec filtres persistants dans l'URL
- [x] Traces natives `run_id` dans le core et timeline operateur dans le cockpit
- [x] Probes MCP synthetiques visibles dans `summary`, `Logs`, `OpsHub` et Grafana
- [x] GPU coherent dans `ops-agent`, `sources` et `summary`

## 2. Observabilite en place

- [x] OTel Collector sain avec OTLP HTTP/gRPC, `/health`, `/metrics` et archivage local durable `traces`/`metrics`
- [x] Loki, Promtail, Prometheus et Grafana provisionnes en code et verifies en live
- [x] `blackbox-exporter` en place pour les services sans `/metrics`
- [x] Dashboards provisionnes:
  - `Mascarade Ops Overview`
  - `Mascarade Service Logs`
  - `Mascarade AI Runtime`
- [x] Smoke OTLP versionne et valide sur trafic reel
- [x] Rapport de cardinalite Loki versionne et exploitation reelle des labels enrichis
- [x] Langfuse raccorde au chemin LLM commun avec traces runtime visibles

## 3. Ce qui reste reellement

- [ ] Etendre Grafana seulement si un nouveau domaine le justifie
- [ ] Recueillir des retours UX a froid sur `Logs` et `OpsHub`
- [ ] Remplacer l'archivage local OTel par un backend plus riche uniquement si la retention/requete transverse devient necessaire

## 4. Complement optionnel

- [ ] Rebrancher `AgentSight` uniquement si un vrai besoin operateur reapparait

## 5. Hors perimetre de ce lot

- [ ] TLS / certificat public
- [ ] Secrets operateur optionnels (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NOTION_TOKEN`)
- [ ] Setup Mac local (`MCP`, `Playwright MCP`)
- [ ] Restes specialises `K-012` / `K-014` portes par `Kill_LIFE`

## 6. Ordre recommande

1. Ne pas rouvrir ce lot sans besoin concret.
2. Sortir d'abord les bundles locaux multi-repo.
3. Garder la ligne `MCP/agentics` sur le backlog specialise `Kill_LIFE/specs/mcp_tasks.md`.
