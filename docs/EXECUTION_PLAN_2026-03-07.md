# Plan d'execution - 7 mars 2026

Plan de reference recale au 8 mars 2026 apres fermeture du backlog RA,
stabilisation du runtime local et ouverture de la phase de consolidation/
publication multi-repo.

---

## Axe 1 - Hygiene repo / publication locale

### Avancement: ~90%

| Action | Statut |
|--------|--------|
| Contrat multi-repo clarifie | FAIT |
| Worktrees regroupes en bundles reviewables | FAIT |
| Premier bundle `mascarade:mcp-runtime-surfaces` | FAIT |
| Deuxieme bundle `mascarade:ops-observability-runtime` | FAIT |
| Publication locale `Kill_LIFE` | FAIT |
| Publication locale `crazy_life` | FAIT |

### Prochain lot
1. Rejouer les checks finaux repo par repo.
2. Decider si la publication distante doit etre lancee maintenant.
3. Ne pas rouvrir de nouveau chantier avant cette decision.

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

### Avancement: ~95%

| Action | Statut |
|--------|--------|
| Cockpit React unifie | FAIT |
| `ops-agent` complet | FAIT |
| `Logs`, `OpsHub`, `Orchestrate` branches | FAIT |
| Probes MCP synthetiques visibles et reprobeables | FAIT |
| GPU coherent dans les surfaces ops | FAIT |
| Dashboards Grafana provisionnes en code | FAIT |
| Extensions UX ou dashboards supplementaires | DIFFERE |

### Prochain lot
1. Ne pas rouvrir sans besoin concret.
2. Traiter seulement les retours UX a froid si necessaire.

---

## Axe 4 - OTel / Loki

### Avancement: ~95%

| Action | Statut |
|--------|--------|
| Exporteurs OTLP core + API | FAIT |
| OTel Collector sain et scrape | FAIT |
| Archivage durable local `traces` / `metrics` | FAIT |
| Parsing Promtail et labels utiles | FAIT |
| Cardinalite Loki verifiee | FAIT |
| Backend analytique plus riche | OPTIONNEL |

### Prochain lot
1. Garder l'archivage local tant qu'il suffit.
2. N'ajouter un backend plus riche que si un besoin d'analyse transverse apparait.

---

## Axe 5 - Fine-tuning local

### Avancement: ~95%

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

### Avancement: ~95%

| Action | Statut |
|--------|--------|
| Auth runtime active | FAIT |
| Surface hote reduite | FAIT |
| Langfuse supporte et sain | FAIT |
| Firecrawl deployee | FAIT |
| Mem0 / OpenMemory deploye | FAIT |
| Docling / Whisper installables dans le venv tools | FAIT |
| Probes Prometheus / blackbox pour services | FAIT |
| TLS public `ACME/DNS` | EXTERNE |
| Cles operateur additionnelles | OPTIONNEL |
| Setup Mac local | EXTERNE |

### Prochain lot
1. Aucun lot local bloquant restant.
2. Ne traiter que les sujets externes ou optionnels sur demande.

---

## Axe 7 - Multi-repo / publication

### Avancement: ~90%

| Action | Statut |
|--------|--------|
| Contrat `crazy_life` / `Kill_LIFE` / `mascarade` | FAIT |
| CI/release sur chemins canoniques | FAIT |
| Bundles locaux documentes | FAIT |
| Commits locaux `mascarade` | FAIT |
| Commits locaux `Kill_LIFE` | FAIT |
| Commits locaux `crazy_life` | FAIT |

### Prochain lot
1. Rejouer les checks minimaux sur les 3 repos.
2. Publier a distance si voulu.
3. Garder les reliquats externes (`K-014`, TLS public, setup Mac) hors de cette phase.

---

## Synthese globale

| Axe | Avancement | Bloqueur principal |
|-----|------------|-------------------|
| 1. Hygiene repo | ~90% | Finir la serie de commits locaux |
| 2. CAD / KiCad | ~90% | Restes specialises externes |
| 3. Cockpit / Obs | ~95% | Aucun blocage critique |
| 4. OTel / Loki | ~95% | Aucun blocage critique |
| 5. Fine-tuning | ~95% | Seulement du suivi optionnel |
| 6. VM / Infra | ~95% | Sujets externes/optionnels |
| 7. Multi-repo | ~95% | Rejouer les checks finaux puis decider du push |

### Priorite immediate recommandee
1. Rejouer les checks minimaux par repo avant toute publication distante.
2. Decider du push repo par repo.
3. Ne pas rouvrir de nouveau chantier tant que la phase de publication n'est pas tranchee.
