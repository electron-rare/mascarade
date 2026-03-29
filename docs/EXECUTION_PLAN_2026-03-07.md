# Plan d'execution - 7 mars 2026

Plan de reference recale au 8 mars 2026 apres fermeture du backlog RA,
stabilisation du runtime local, consolidation multi-repo et livraison du lot
observabilite/proxy operateur.

---

## Axe 1 - Hygiene repo / publication locale

### Avancement: ~100%

| Action | Statut |
|--------|--------|
| Contrat multi-repo clarifie | FAIT |
| Worktrees regroupes en bundles reviewables | FAIT |
| Premier bundle `mascarade:mcp-runtime-surfaces` | FAIT |
| Deuxieme bundle `mascarade:ops-observability-runtime` | FAIT |
| Publication locale `Kill_LIFE` | FAIT |
| Publication locale `crazy_life` | FAIT |
| Publication distante des lots precedents | FAIT |

### Prochain lot
1. Aucun lot repo/hygiene bloquant local restant.
2. Le seul lot encore ouvert dans `mascarade` est un follow-up documentaire de cloture.
3. Ne rouvrir une vague multi-repo que si un nouveau besoin de publication apparait.

---

## Axe 2 - CAD / KiCad

### Avancement: ~90%

| Action | Statut |
|--------|--------|
| Sous-modules et helpers CAD | FAIT |
| Runtime MCP `freecad` / `openscad` | FAIT |
| Documentation et smokes de base | FAIT |
| `K-012` `pcbnew` host-native | EXTERNE |
| `K-014` `NEXAR_TOKEN` live | EXTERNE |

### Prochain lot
1. Ne rouvrir ce chantier que sur machine/support adequat.
2. Garder `K-012` / `K-014` comme restes specialises hors backlog RA.

---

## Axe 3 - Cockpit / Observability

### Avancement: ~100%

| Action | Statut |
|--------|--------|
| Cockpit React unifie | FAIT |
| `ops-agent` complet | FAIT |
| `Logs`, `OpsHub`, `Orchestrate` branches | FAIT |
| Probes MCP synthetiques visibles et reprobeables | FAIT |
| GPU coherent dans les surfaces ops | FAIT |
| Dashboards Grafana provisionnes en code | FAIT |
| `Agent Zero` en mode operator copilot | FAIT |
| Surfaces publiques/proxifiees dans `OpsHub` | FAIT |
| `ZeroClaw` live + `zeroclaw-docs` / `LangGraph` visibles comme surfaces operateur (runtime `ZeroClaw` on-demand) | FAIT |
| `SearXNG` / `Paperless-ngx` / `Karakeep` publies comme surfaces operateur `phase2` derriere `edge-proxy` | FAIT |
| Lane industrielle enrichie avec posture `PLM/QMS/WMS` `generic-rest` live-ready, compteurs topo `site/partner/line`, et proxy `industrial.saillant.cc` revalide | FAIT |
| Extensions UX ou dashboards supplementaires | DIFFERE |

### Prochain lot
1. Ne pas rouvrir sans besoin concret.
2. Traiter seulement les retours UX a froid si necessaire.
3. Le sandbox `DCS` local est maintenant en place; ne rouvrir la suite industrielle que pour un vrai runtime/contrat OT externe.

---

## Axe 4 - OTel / Loki

### Avancement: ~100%

| Action | Statut |
|--------|--------|
| Exporteurs OTLP core + API | FAIT |
| OTel Collector sain et scrape | FAIT |
| `Tempo` branche comme backend traces | FAIT |
| Parsing Promtail et labels utiles | FAIT |
| Cardinalite Loki verifiee | FAIT |
| Backend analytique plus riche que `Tempo` | OPTIONNEL |

### Prochain lot
1. Garder `Tempo + Loki + Prometheus` comme trilogie nominale.
2. N'ajouter un backend plus riche que si un besoin d'analyse transverse apparait.

---

## Axe 5 - Fine-tuning local

### Avancement: ~100%

| Action | Statut |
|--------|--------|
| Pipeline distill -> merge -> train | FAIT |
| Queue GPU + verrou global + `--resume` | FAIT |
| Batch canonique `train=completed` | FAIT |
| Promotions locales `esp32/spice/pio` | FAIT |
| Export GGUF + chargement Ollama | FAIT |
| `Agent Zero` evalue hors chemin critique | FAIT |
| Benchmark `gpu_slots=2` canonique | DIFFERE |

### Prochain lot
1. Ne rouvrir que si un nouveau besoin modele apparait.
2. Garder `Agent Zero` hors pipeline critique.

---

## Axe 6 - VM / Infra

### Avancement: ~100%

| Action | Statut |
|--------|--------|
| Auth runtime active | FAIT |
| Surface hote reduite | FAIT |
| Langfuse supporte et sain | FAIT |
| Langfuse branche au runtime LLM | FAIT |
| Firecrawl deployee | FAIT |
| Mem0 / OpenMemory deploye | FAIT |
| Docling / Whisper installables dans le venv tools | FAIT |
| Probes Prometheus / blackbox pour services | FAIT |
| `Grafana` / `Langfuse` publies derriere `edge-proxy` | FAIT |
| `ZeroClaw` live + `zeroclaw-docs` / `LangGraph` publies derriere `edge-proxy` | FAIT |
| `SearXNG` / `Paperless-ngx` / `Karakeep` deployee via `deploy/phase2` et publies derriere `edge-proxy` | FAIT |
| TLS public `ACME/DNS` | FAIT |
| `openai` active et validee en strict | FAIT |
| `claude` configuree mais bloquee par credit Anthropic | EXTERNE |
| `google` configure avec `api_key` mais bloquee par `generativelanguage.googleapis.com` desactive | EXTERNE |
| Setup Mac local | FAIT |

### Prochain lot
1. Le bind public `edge-proxy` est ouvert et le certificat Let's Encrypt wildcard (`saillant.cc`, `*.saillant.cc`) est installe.
2. `OpenAI` est maintenant validee en strict; les restes providers sont externes: billing `Anthropic` et activation de l'API Google Generative Language.
3. `ZeroClaw` est maintenant installe nativement sur la VM, avec demarrage a la demande; `zeroclaw.saillant.cc` sert la surface live, tandis que `zeroclaw-docs.saillant.cc` et `langgraph.saillant.cc` gardent les runbooks operateur.
4. Le chemin provider hybride n'est plus theorique: un smoke reel `POST /webhook` via le gateway natif repond `200` avec `OpenRouter`.
5. La stack `deploy/phase2` est en service: `SearXNG`, `Paperless-ngx` et `Karakeep` restent binds en loopback et sont exposes via `search.saillant.cc`, `paperless.saillant.cc` et `karakeep.saillant.cc`.
6. Le setup Mac local est maintenant valide sur le poste cible: `codex --apply` a enregistre `kicad`, `validate-specs`, `knowledge-base`, `github-dispatch`, `freecad`, `openscad`, `huggingface` et `playwright`, et `Playwright MCP` repond.

---

## Axe 7 - Multi-repo / publication

### Avancement: ~95%

| Action | Statut |
|--------|--------|
| Contrat `crazy_life` / `Kill_LIFE` / `mascarade` | FAIT |
| CI/release sur chemins canoniques | FAIT |
| Bundles locaux documentes | FAIT |
| Commits locaux `mascarade` | FAIT |
| Commits locaux `Kill_LIFE` | FAIT |
| Commits locaux `crazy_life` | FAIT |
| Push des lots precedents | FAIT |

### Prochain lot
1. Aucun reliquat repo critique restant apres fermeture du follow-up industriel `PLM/QMS/WMS` dans `agent-factory-cockpit` et `mascarade`.
2. Garder les reliquats externes (`K-014`, billing `Anthropic`, activation API Google) hors de cette phase.
3. Ne pas rouvrir de nouvelle consolidation inter-repo sans besoin concret.

---

## Synthese globale

| Axe | Avancement | Bloqueur principal |
|-----|------------|-------------------|
| 1. Hygiene repo | ~95% | Aucun blocage critique |
| 2. CAD / KiCad | ~90% | Restes specialises externes |
| 3. Cockpit / Obs | ~100% | Aucun blocage critique |
| 4. OTel / Loki | ~100% | Aucun blocage critique |
| 5. Fine-tuning | ~95% | Seulement du suivi optionnel |
| 6. VM / Infra | ~100% | Plus de bloc local; seulement des sujets externes/optionnels |
| 7. Multi-repo | ~100% | Aucun blocage critique |

### Priorite immediate recommandee
1. Ne pas rouvrir de nouveau chantier local sans besoin concret.
2. Traiter seulement les sujets externes ou optionnels: billing `Anthropic`, activation API Google, quota/token `NEXAR` si le sourcing live repart, et consolidation du worktree local sur le Mac operateur avant tout `pull`.
3. Si une nouvelle vague repo s'ouvre, repartir d'un lot neuf au lieu de reutiliser un reliquat historique.
4. Pour tout nouveau reliquat local, passer d'abord par:
   `bash scripts/run_next_useful_lot.sh`
   puis utiliser
   [docs/NEXT_USEFUL_LOT_STATE.md](docs/NEXT_USEFUL_LOT_STATE.md)
   comme handoff court terme.
