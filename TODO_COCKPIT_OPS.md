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

- [x] OTel Collector sain avec OTLP HTTP/gRPC, `/health`, `/metrics` et export traces vers `Tempo`
- [x] Loki, Promtail, Prometheus et Grafana provisionnes en code et verifies en live
- [x] `blackbox-exporter` en place pour les services sans `/metrics`
- [x] Dashboards provisionnes:
  - `Mascarade Ops Overview`
  - `Mascarade Service Logs`
  - `Mascarade AI Runtime`
  - `Mascarade Tooling Observability`
- [x] Smoke OTLP versionne et valide sur trafic reel
- [x] Rapport de cardinalite Loki versionne et exploitation reelle des labels enrichis
- [x] Langfuse raccorde au chemin LLM commun avec traces runtime visibles
- [x] `Tempo` branche comme backend traces Grafana
- [x] `Grafana` et `Langfuse` exposes comme surfaces operateur derriere `edge-proxy`
- [x] `OpsHub` distingue maintenant posture runtime, observabilite et surfaces publiques/proxifiees

## 3. Ce qui reste reellement

- [ ] Etendre Grafana seulement si un nouveau domaine le justifie
- [ ] Recueillir des retours UX a froid sur `Logs` et `OpsHub`
- [ ] Ouvrir publiquement le proxy uniquement si le chemin `DNS/ACME` doit vraiment etre active
- [ ] Etendre les actions operateur d'`Agent Zero` uniquement si un usage concret depasse le mode copilot actuel

## 4. Complement optionnel

- [ ] Rebrancher `AgentSight` uniquement si un vrai besoin operateur reapparait

## 5. Hors perimetre de ce lot

- [ ] TLS / certificat public
- [ ] Secrets operateur optionnels (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NEXAR_TOKEN`)
- [ ] Setup Mac local (`MCP`, `Playwright MCP`)
- [ ] Si le sourcing Nexar live devient critique, prevoir un token/plan avec quota de parts non nul
- [ ] `K-012` uniquement si le host-native KiCad redevient requis

## 6. Ordre recommande

1. Ne pas rouvrir ce lot sans besoin concret.
2. Considerer le lot cockpit/ops comme livre apres rejeu vert des checks canoniques du `2026-03-08`.
3. Garder la ligne `MCP/agentics` sur le backlog specialise `Kill_LIFE/specs/mcp_tasks.md`.
4. Traiter separement les sujets externes: `DNS/ACME`, secrets providers, setup Mac local.
5. Ne pas traiter le repo compagnon `finetune/kicad_kic_ai` comme un delta `mascarade`; il suit sa propre publication.
