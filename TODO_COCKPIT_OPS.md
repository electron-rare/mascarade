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
- [x] `Firecrawl`, `Mem0`, `Prometheus` et `Ollama` exposes comme surfaces operateur derriere `edge-proxy`
- [x] `ZeroClaw` expose comme surface live on-demand derriere `edge-proxy`, avec `zeroclaw-docs` et `LangGraph` gardes comme surfaces runbook
- [x] Le monitor ops voit `ZeroClaw` en live, et le runtime natif a ete smoke-teste sur un appel reel via `OpenRouter`
- [x] `Industrial Cockpit` expose comme surface operateur derriere `edge-proxy` sur `industrial.saillant.cc`, avec inventory des 7 serveurs MCP industriels visible dans `OpsHub`
- [x] `industrial.saillant.cc/` et `industrial.saillant.cc/api/session` repondent `200` avec auth operateur; aucun port brut n'est expose pour ce cockpit
- [x] `SearXNG`, `Paperless-ngx` et `Karakeep` sont exposes comme surfaces operateur derriere `edge-proxy`, avec URLs proxifiees dans `OpsHub` et verification live dans `/api/ops/monitor`
- [x] `PLM` remonte maintenant dans la lane industrielle avec son contrat MCP explicite (`health` + `contract`) et un statut par operation `live` / `simulated` / `blocked`
- [x] `QMS` remonte maintenant dans la lane industrielle avec son contrat MCP explicite (`health` + `contract`) et un statut par operation `live` / `simulated` / `blocked`
- [x] Integrer un sandbox `DCS` gouverne local a la lane industrielle pour disposer d'un flux live-ready de demo sans write direct OT
- [x] `Infrastructure` expose maintenant les compteurs de topologie industrielle utiles (`sites`, `external partners`, `lines`) pour le rollout `grandris-1` / `ems-lyon`
- [x] `OpsHub` distingue maintenant posture runtime, observabilite et surfaces publiques/proxifiees
- [x] `OpsHub` n'ouvre plus les surfaces tooling sur des ports bruts; il renvoie vers les hostnames proxifies proteges

## 3. Ce qui reste reellement

- [ ] Etendre Grafana seulement si un nouveau domaine le justifie
- [ ] Recueillir des retours UX a froid sur `Logs` et `OpsHub`
- [ ] Etendre les actions operateur d'`Agent Zero` uniquement si un usage concret depasse le mode copilot actuel
- [ ] N'etendre la stack `phase2` (`SearXNG`, `Paperless-ngx`, `Karakeep`) que si un workflow documentaire/recherche concret le justifie
- [ ] Etendre le cockpit industriel seulement si un besoin reel depasse l'inventaire/runtime/tool-proxy actuel
- [ ] Ne rouvrir `DCS` live externe qu'avec un vrai runtime/contrat OT; `WMS` est deja qualifie en `generic-rest` live-ready et reste volontairement `simulated` sur cette VM tant que le sandbox n'est pas configure

## 4. Complement optionnel

- [ ] Rebrancher `AgentSight` uniquement si un vrai besoin operateur reapparait

## 5. Hors perimetre de ce lot

- [x] TLS / certificat public et DNS `*.saillant.cc`
- [ ] Sujets externes providers/secrets: billing `Anthropic`, activation API Google, quota/token `NEXAR` si un sourcing live repart
- [x] Setup Mac local (`MCP`, `Playwright MCP`) valide sur le poste operateur cible
- [ ] Si le sourcing Nexar live devient critique, prevoir un token/plan avec quota de parts non nul
- [ ] `K-012` uniquement si le host-native KiCad redevient requis

## 6. Ordre recommande

1. Ne pas rouvrir ce lot sans besoin concret.
2. Considerer le lot cockpit/ops comme livre apres rejeu vert des checks canoniques du `2026-03-08`.
3. Garder la ligne `MCP/agentics` sur le backlog specialise `Kill_LIFE/specs/mcp_tasks.md`.
4. Traiter separement les sujets externes: billing `Anthropic`, activation API Google, quota `NEXAR` si besoin live.
5. Ne pas traiter le repo compagnon `finetune/kicad_kic_ai` comme un delta `mascarade`; il suit sa propre publication.

## 7. Automation

Pour reprendre le lot local actif sans requalifier tout le contexte a la main:

```bash
cd /home/clems/mascarade
bash scripts/run_next_useful_lot.sh
```

Le snapshot genere par le script vit dans
[NEXT_USEFUL_LOT_STATE.md](/home/clems/mascarade/docs/NEXT_USEFUL_LOT_STATE.md).
