# Plan d'execution - 7 mars 2026

Plan court, factuel, base sur l'etat reel du repo au 7 mars 2026.
Mis a jour apres audit croise complet code/docs.

---

## Axe 1 - Stabilisation locale / hygiene repo

### Avancement: ~60%

| Action | Statut |
|--------|--------|
| Choix CPU coherent dans finetune | FAIT — serie par defaut, parallel derriere env guard |
| model_selector.py isole comme experimental | FAIT — standalone + integration opt-in dans run_local.py |
| Remediations MCP dans sous-modules KiCad | FAIT — submodules pointes vers electron-rare, commites |
| crazy_life propre | FAIT — repo clean, CI presente, README versionne (R-005 resolu) |
| Derives docs crazy_life | OUVERT — sync_crazy_life.sh existe, contrat multi-repo non clarifie (R-010) |
| Worktree non melange | OUVERT — encore des fichiers non commites multi-sujets |

### Prochain lot
1. Commiter les fichiers github_dispatch en attente.
2. Decider du sort des fichiers _REAUDIT non suivis.
3. Clarifier le contrat multi-repo (R-010).

---

## Axe 2 - CAD / KiCad

### Avancement: ~85%

| Action | Statut |
|--------|--------|
| Sous-modules electron-rare | FAIT — commite et pushe |
| Section CAD dans ./config | FAIT |
| Actions --cad-* dans ./setup | FAIT |
| Helpers plugins/doctor/cad_stack.sh | FAIT |
| Recapitulatif CAD dans ./config | FAIT |
| Actions CAD post-setup interactif | FAIT |
| Smoke CAD dans TUI | OUVERT |
| Doc chemins plugins par OS | OUVERT |
| Doctor MCP dedie | OUVERT |

### Prochain lot
1. Smoke operateur CAD dans la TUI.
2. Doc courte chemins plugins par OS.

---

## Axe 3 - Cockpit / Observability

### Avancement: ~85%

| Action | Statut |
|--------|--------|
| Cockpit React unifie | FAIT |
| Pages operations (Dashboard, Metrics, Infra, Logs) | FAIT |
| agent-zero visible | FAIT |
| Trace inter-agent native run_id | FAIT |
| ops-agent complet | FAIT — /health, /sources, /summary, /logs/recent, /logs/stream |
| /api/ops/logs/recent | FAIT |
| /api/ops/logs/query (Loki) | FAIT — filtres source/severity/run_id/since/q |
| /api/ops/logs/stream (SSE) | FAIT |
| /api/ops/summary + MCP probe | FAIT — probeMcpRuntime() avec cache TTL |
| Mode history Logs frontend | FAIT — toggle live/history, fenetres 15m/1h/6h/24h |
| Exporteurs OTel core | FAIT — otel.py, OTLP HTTP custom |
| Exporteurs OTel API | FAIT — otel.ts, OTLP HTTP custom |
| Auth routes ops | FAIT — middleware timing-safe bearer+cookie |
| OTel Collector config reelle | OUVERT — stub debug-only |
| Grafana datasources en code | OUVERT |
| Probe GPU (nvidia-smi) | OUVERT |

### Prochain lot
1. Configurer le vrai exporter OTel Collector.
2. Configurer Grafana datasources (Loki + Prometheus).
3. Probe GPU dans ops-agent.

---

## Axe 4 - OTel / Loki

### Avancement: ~60%

| Action | Statut |
|--------|--------|
| loki deploye + healthcheck | FAIT |
| promtail deploye (Docker + journald) | FAIT |
| otel-collector deploye | FAIT |
| OTEL_ENABLED=true dans compose | FAIT |
| Exporteurs OTLP core + API | FAIT |
| Collector exporte vers backend reel | OUVERT — debug-only actuellement |
| Promtail parsing JSON structure | OUVERT |
| Labels Loki utiles | OUVERT |

### Prochain lot
1. Remplacer l'exporter debug du Collector par Loki.
2. Enrichir Promtail pour les logs JSON.
3. Verifier les labels Loki.

---

## Axe 5 - Fine-tuning local

### Avancement: ~65%

| Action | Statut |
|--------|--------|
| Pipeline distill -> merge -> train | FAIT |
| Support CPU + GPU | FAIT |
| Queue GPU + garde-fous VRAM | FAIT |
| --resume fonctionnel | FAIT |
| batch_status.py (distill/train) | FAIT |
| model_selector.py + selected_model.json | FAIT |
| Export GGUF (4 formats) | FAIT |
| Deploy GGUF vers Ollama | FAIT |
| Batch train=completed | OUVERT — bloqueur principal |
| Doc operateur --resume | OUVERT |
| Benchmark gpu_slots 1 vs 2 | OUVERT |
| Pre-validation datasets | OUVERT — existence check seulement |
| Integration modeles dans Mascarade | OUVERT |

### Prochain lot
1. Valider un batch complet train=completed.
2. Ecrire la doc operateur --resume.
3. Benchmark GPU slots.

---

## Axe 6 - VM / Infra

### Avancement: ~45%

| Action | Statut |
|--------|--------|
| Ports en 127.0.0.1 | FAIT |
| Middleware auth implemente | FAIT |
| Auth active (.env rempli) | OUVERT — MASCARADE_API_KEY="" |
| Rotation Postgres | FAIT |
| CrewAI + OpenAI Agents SDK | FAIT |
| GraphRAG | FAIT |
| Claude Code MCP config VM | FAIT |
| edge-proxy nginx | FAIT — pas de TLS |
| Langfuse ZodError | CLOS — service supporte et runtime sain, optionnel hors profil standard |
| Cles API .env (Anthropic/OpenAI/Notion) | OUVERT |
| Firecrawl | PARTIEL — image officielle retenue, secret/API cible manquant |
| Mem0 | PARTIEL — compose migration seulement |
| Docling / Whisper | OUVERT |
| Reverse proxy HTTPS | OUVERT |
| Grafana dashboards | OUVERT |
| Prometheus scrape services | OUVERT |
| Pression memoire (R-001) | OUVERT |
| Faux-verts healthchecks (R-003) | OUVERT |

### Prochain lot
1. Remplir MASCARADE_API_KEY dans .env (critique).
2. Reduire pression memoire/swap (R-001).
3. Corriger faux-verts healthchecks (R-003).

---

## Axe 7 - Multi-repo / Kill_LIFE

### Avancement: ~70%

| Action | Statut |
|--------|--------|
| crazy_life propre + CI | FAIT |
| Kill_LIFE 19 workflows CI | FAIT |
| Zeroclaw dual HW todo (69/70 items) | FAIT |
| I-205 validation e2e Docker | OUVERT |
| ci_runtime.py / scope_policy.py | ABSENT — references cassees |
| ai-agentic-embedded-base single source | OUVERT — duplique dans Kill_LIFE |
| Contrat multi-repo (R-010) | OUVERT |
| CI renforcee (R-011) | PARTIEL |

### Prochain lot
1. Nettoyer les references a ci_runtime.py / scope_policy.py.
2. Valider I-205 (integrations Docker).
3. Decider ai-agentic-embedded-base.

---

## Synthese globale

| Axe | Avancement | Bloqueur principal |
|-----|------------|-------------------|
| 1. Hygiene repo | ~60% | Worktree encore melange, contrat multi-repo |
| 2. CAD / KiCad | ~85% | Smoke TUI, doc OS |
| 3. Cockpit / Obs | ~85% | OTel Collector stub, Grafana, probe GPU |
| 4. OTel / Loki | ~60% | Collector debug-only |
| 5. Fine-tuning | ~65% | Batch train=completed jamais atteint |
| 6. VM / Infra | ~45% | Auth desactivee, memoire, healthchecks |
| 7. Multi-repo | ~70% | References cassees, ai-agentic-base |

### Priorite immediate recommandee
1. **VM critique**: activer auth + reduire pression memoire + fixer healthchecks
2. **Fine-tuning**: valider un batch train=completed
3. **OTel**: remplacer le stub Collector par un vrai exporter
