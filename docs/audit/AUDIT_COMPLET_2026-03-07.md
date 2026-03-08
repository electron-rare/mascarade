# Audit complet Mascarade — 7 mars 2026

Audit croise entre les TODO documentes et l'etat reel du code/infra.

Legende:
- `FAIT` — implemente et verifie dans le code
- `PARTIEL` — commence mais incomplet
- `OUVERT` — pas encore fait
- `OBSOLETE` — plus pertinent
- `CORRIGE` — le TODO disait "a faire" mais c'est deja fait

---

## 1. VM / Infra (TODO_VM.md)

### Langfuse
| Item | TODO | Etat reel |
|------|------|-----------|
| Container stable | OUVERT | Worker + Web deployes dans docker-compose, mais ZodError non resolu |
| Health endpoint | OUVERT | Pas de healthcheck defini sur langfuse-web/worker |
| Desactive par defaut | FAIT | Profile `heavy`, decision actee |

### Cles API
| Item | TODO | Etat reel |
|------|------|-----------|
| Remplir .env sur VM | OUVERT | `.env` existe, `MASCARADE_API_KEY=""` (vide = auth desactivee) |
| Copier .env pour tools | FAIT | Synchronisation effectuee |
| ANTHROPIC/OPENAI/MISTRAL/NOTION | OUVERT | Seul MISTRAL et AWS Bedrock sont renseignes dans .env |

### Firecrawl
| Item | TODO | Etat reel |
|------|------|-----------|
| Deploiement | PARTIEL | Support repo en cours d'integration autour de `mcp/firecrawl` |
| Image alternative | FAIT | Image officielle retenue: `mcp/firecrawl` |

### Mem0
| Item | TODO | Etat reel |
|------|------|-----------|
| Deploiement | PARTIEL | Present dans `deploy/migration/compose.tools.ai.yml` (profile heavy), absent du compose principal |

### Outils Python
| Item | TODO | Etat reel |
|------|------|-----------|
| GraphRAG | FAIT | Installe dans ~/tools/python-tools/.venv |
| Docling | OUVERT | Installation interrompue |
| Whisper | OUVERT | Installation interrompue |

### Deps Mascarade
| Item | TODO | Etat reel |
|------|------|-----------|
| CrewAI | FAIT | Dans core/pyproject.toml |
| OpenAI Agents SDK | FAIT | Ajoute comme dependance |

### MCP Servers (Mac)
| Item | TODO | Etat reel |
|------|------|-----------|
| @anthropic-ai/mcp | OUVERT | Non installe |
| Playwright MCP | OUVERT | Non installe |
| Claude Code config VM | FAIT | ~/.claude/settings.json configure |

### Securite
| Item | TODO | Etat reel |
|------|------|-----------|
| Ports en 127.0.0.1 | FAIT | Tous les ports locaux |
| Reverse proxy HTTPS | OUVERT | edge-proxy (nginx) existe mais pas de TLS |
| Auth Bearer | CORRIGE | Middleware implemente (timing-safe, bearer+cookie) mais DESACTIVE (.env vide) |
| Rotation Postgres | FAIT | Effectuee |

### Monitoring
| Item | TODO | Etat reel |
|------|------|-----------|
| Langfuse tracing | OUVERT | Bloque par le ZodError |
| Grafana dashboards | OUVERT | Grafana deploye, aucun datasource/dashboard configure en code |
| Prometheus endpoints | PARTIEL | Prometheus deploye, scrape Prometheus lui-meme, pas les services applicatifs |

---

## 2. Fine-Tuning (TODO_TUNNING_PARTY.md + TODO_IMPLEMENTE.md)

### Pipeline local
| Item | TODO | Etat reel |
|------|------|-----------|
| Pipeline distill -> merge -> train | FAIT | Fonctionnel, teste |
| Support CPU + GPU | FAIT | train_local.py (GPU), train_cpu.py (CPU) |
| Distillation teacher via API locale | FAIT | 127.0.0.1:8100, Mistral JSON strict |
| Queue GPU + garde-fous VRAM | FAIT | probe_vram_mb(), slot limiting, Ollama unload |
| Resume --resume | FAIT | load_resume_manifest(), skip domains completed |
| batch_status.py | FAIT | Distingue distill/train par domaine |
| model_selector.py | FAIT | HF Hub search, ranking, cache 24h, selected_model.json |

### Backlog immediat
| Item | TODO | Etat reel |
|------|------|-----------|
| Batch complet train=completed | OUVERT | Tous les runs restent en train=pending |
| Doc reprise --resume | OUVERT | Code fonctionne, doc operateur manquante |
| Resume CLI lisible | CORRIGE | batch_status.py fait deja la distinction distill/train |

### Priorite suivante
| Item | TODO | Etat reel |
|------|------|-----------|
| Comparer gpu_slots 1 vs 2 | OUVERT | Logique implementee, pas de benchmark fait |
| Pre-validation datasets | PARTIEL | Existence check seulement, pas de validation contenu |
| Rapport source/distilled/merged rows | OUVERT | Pas de rapport agrege |

### Post-stabilisation
| Item | TODO | Etat reel |
|------|------|-----------|
| Export GGUF | FAIT | pipeline.py step_gguf() complet (q4_k_m, q4_k_s, q5_k_m, q8_0) |
| Deploy GGUF vers Ollama | FAIT | pipeline.py step_deploy() via docker cp/exec |
| Integration modeles dans Mascarade | OUVERT | Pipeline pret, pas encore de modele promu |
| Agent Zero evaluation | OUVERT | Perimetre non cadre |
| selected_model.json lu par run_local | CORRIGE | run_local.py importe resolve_model() au boot |
| selected_model.json lu par batch_local | OUVERT | batch_local hardcode --student-model |
| Benchmark model_selector vs manuel | OUVERT | Pas fait |

---

## 3. Cockpit / Ops / Observability (TODO_COCKPIT_OPS.md)

### Deja livre
| Item | TODO | Etat reel |
|------|------|-----------|
| Cockpit React unifie | FAIT | Shell, navigation, responsive, clavier |
| Pages operations refondues | FAIT | Dashboard, Metrics, Infrastructure, Logs |
| agent-zero visible | FAIT | Lane lead dans le cockpit |
| Trace inter-agent native | FAIT | run_id, evenements structures, buffer recent |
| Lane Logs | FAIT | Branchee traces + incidents |
| Routes API facade | FAIT | summary, sources, logs/recent, agent-traces/* |
| Scaffolding Docker obs | FAIT | loki, promtail, otel-collector dans compose |

### Blocages documentes vs etat reel
| Item | TODO disait | Etat reel |
|------|-------------|-----------|
| Finaliser ops-agent | OUVERT | CORRIGE — ops-agent COMPLET: /health, /sources, /summary, /logs/recent, /logs/stream, collecte Docker+journald |
| /api/ops/logs/query (Loki) | OUVERT | CORRIGE — IMPLEMENTE: query_range Loki, filtres source/q/run_id/agent/severity/since |
| Mode history page Logs | OUVERT | CORRIGE — IMPLEMENTE: toggle live/history, fenetres 15m/1h/6h/24h, recherche texte |
| Exporteurs OTel core | OUVERT | CORRIGE — IMPLEMENTE: otel.py custom OTLP HTTP, schedule_otlp_log(), OTEL_ENABLED |
| Exporteurs OTel API | OUVERT | CORRIGE — IMPLEMENTE: otel.ts custom OTLP HTTP, emitStructuredLog() |

### Ce qui reste reellement
| Item | Etat reel |
|------|-----------|
| OTel Collector config | STUB — recoit OTLP mais exporte uniquement en debug (stdout), pas vers Loki/backend |
| Grafana datasources | OUVERT — aucun datasource configure en code |
| Filtres Logs avances | PARTIEL — filtres source/severity/run_id/service implementes, routing_role/provider/model presents |
| Auth sur routes ops | FAIT — middleware auth applique sur toutes les routes /api/* |

---

## 4. MCP Runtime (MCP_RUNTIME_TODO + MCP_BACKLOG)

### Implemente
| ID | Description | Etat |
|----|-------------|------|
| M-001 | Data dir writable JLCPCB | FAIT |
| M-002 | Decouvrir libs KiCad reelles | FAIT |
| M-003 | Smoke test STDIO versionne | FAIT |
| M-004 | Chemin NEXAR_TOKEN | FAIT |
| M-005 | Backends reels (plus de mocks) | FAIT |
| M-006 | Branchement conteneur KiCad v10 | FAIT |
| M-007 | Index SQLite auxiliaire | FAIT |
| M-008 | Etat synthetique ops | FAIT — probeMcpRuntime() dans ops.ts avec cache TTL |
| M-009 | Alignement protocole MCP | FAIT — matrice documentee |
| M-011 | Statut micro-serveurs auxiliaires | FAIT — classes comme surfaces supportees |
| B-001 | Alignement protocoles | FAIT |
| B-002 | Observabilite synthetique | FAIT — /api/ops/summary expose bloc mcp |
| B-004 | Serveurs notion + github-dispatch | FAIT — code ecrit, github_dispatch pas encore commite |

### Reste ouvert
| ID | Description | Etat |
|----|-------------|------|
| M-010 | Boot host-native avec pcbnew | OUVERT |
| B-003 | Revalidation host-native | OUVERT |
| B-005 | nexar_api mode live | OUVERT |

---

## 5. CAD / KiCad (TODO_CAD_KICAD.md)

| Item | TODO | Etat reel |
|------|------|-----------|
| Sous-modules enregistres | FAIT | .gitmodules pointe vers electron-rare |
| Wrapper install_kicad_plugins.sh | FAIT | list, plugin-dir, install, doctor |
| Stack CAD cad_stack.sh | FAIT | up, down, ps, doctor, mcp |
| Section CAD dans ./config | FAIT | Implementee |
| Actions --cad-* dans ./setup | FAIT | --cad-plugins, --cad-doctor, --cad-stack |
| Recapitulatif CAD dans ./config | FAIT | Affiche |
| Actions CAD post-setup interactif | FAIT | Proposees |
| Smoke CAD dans TUI | OUVERT | |
| Doc chemins plugins par OS | OUVERT | |
| Doctor MCP dedie | OUVERT | |

---

## 6. Remediation multi-repo (REMEDIATION_BACKLOG)

### J0 — Immediat
| ID | Description | Etat reel |
|----|-------------|-----------|
| R-001 | Reduire pression memoire/swap | OUVERT — pas de plafond d'execution documente |
| R-002 | Reactiver auth effective | PARTIEL — middleware pret, .env vide |
| R-003 | Faux-verts healthchecks | OUVERT — pas de correction observee |
| R-004 | Tests Python executables | OUVERT — pas de doc bootstrap |
| R-005 | Geler crazy_life | CORRIGE — repo propre, git status clean, 2 workflows CI, README present |

### J7 — Une semaine
| ID | Description | Etat reel |
|----|-------------|-----------|
| R-006 | Observabilite machine cockpit | PARTIEL — ops-agent fonctionne, pas de probe GPU |
| R-007 | Builds hermetiques | OUVERT — pas de politique artefacts documentee |
| R-008 | Reduire drift Kill_LIFE | OUVERT — worktree toujours melange |
| R-009 | Sort de ai-agentic-embedded-base | OUVERT — toujours duplique dans Kill_LIFE/, role "socle methodologique" |

### J30 — Durable
| ID | Description | Etat reel |
|----|-------------|-----------|
| R-010 | Contrat multi-repo | OUVERT — sync_crazy_life.sh existe et fonctionne |
| R-011 | CI crazy_life + Kill_LIFE | PARTIEL — crazy_life a 2 workflows, Kill_LIFE en a 19 |
| R-012 | Surface exposee hote | OUVERT |
| R-013 | Workflow Editor Lot 2 | OUVERT — lot 1 termine |
| R-014 | Fine-tuning hors critique | OUVERT |
| R-015 | KiCad MCP roadmap v2+ | OUVERT |

---

## 7. Kill_LIFE (zeroclaw_dual_hw_todo.md)

| Section | Etat |
|---------|------|
| I-001 a I-008 (immediat) | FAIT |
| D-001 a D-006 (daily) | FAIT |
| H-001 a H-003 (hardware) | FAIT |
| C-001 a C-003 (cost) | FAIT |
| E-001 a E-004 (exit) | FAIT |
| I-201 a I-204 (integrations) | FAIT |
| I-205 (validation e2e Docker) | OUVERT |

Scripts references manquants:
- `tools/ci_runtime.py` — ABSENT du repo
- `tools/scope_policy.py` — ABSENT du repo

---

## 8. Fichiers non commites dans mascarade

| Fichier | Nature | Action |
|---------|--------|--------|
| core/mascarade/integrations/__init__.py | Export GitHubDispatchClient | A commiter |
| core/mascarade/integrations/github_dispatch.py | Nouveau client MCP | A commiter |
| core/tests/test_github_dispatch.py | Tests du client | A commiter |
| finetune/kicad_kic_ai | Contenu modifie submodule | A evaluer |
| finetune/kicad_mcp_server | Contenu modifie submodule | A evaluer |

---

## 9. Synthese par priorite

### Corrections d'audit (TODOs marques "a faire" mais deja faits)

Ces items etaient documentes comme ouverts mais sont en realite implementes:

1. **ops-agent** — complet avec /health, /sources, /summary, /logs/recent, /logs/stream
2. **/api/ops/logs/query** — requete Loki implementee avec filtres complets
3. **Mode history Logs** — toggle live/history avec fenetres temporelles
4. **Exporteurs OTel core + API** — custom OTLP HTTP implemente des deux cotes
5. **batch_status.py** — distingue distill/train par domaine
6. **selected_model.json** — lu par run_local.py au boot
7. **Export GGUF** — pipeline.py complet avec 4 formats de quantification
8. **Deploy GGUF Ollama** — pipeline.py step_deploy() fonctionnel
9. **crazy_life** — repo propre, CI presente, README versionne

### Vrais bloqueurs restants

| Priorite | Item | Scope |
|----------|------|-------|
| CRITIQUE | Auth desactivee (.env vide) | VM |
| CRITIQUE | Pression memoire non plafonnee | VM |
| CRITIQUE | Faux-verts healthchecks | VM |
| HAUTE | Batch train=completed jamais atteint | Fine-tuning |
| HAUTE | OTel Collector stub (debug only) | Observability |
| HAUTE | Grafana sans datasources | Monitoring |
| MOYENNE | Probe GPU absent | Observability |
| MOYENNE | Pre-validation datasets | Fine-tuning |
| MOYENNE | Boot host-native KiCad (M-010) | MCP |
| MOYENNE | nexar_api live (B-005) | MCP |
| MOYENNE | ai-agentic-embedded-base non resolu | Kill_LIFE |
| BASSE | Docling/Whisper | VM |
| BASSE | MCP Mac (Playwright) | VM |
| BASSE | Workflow Editor Lot 2 | crazy_life |
