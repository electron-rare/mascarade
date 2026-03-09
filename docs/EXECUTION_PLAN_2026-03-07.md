# Plan d'execution - 7 mars 2026

Plan court, factuel, base sur l'etat reel du repo au 7 mars 2026.
Mis a jour apres audit croise complet code/docs.

---

## Axe 1 - Stabilisation locale / hygiene repo

### Avancement: ~60%

| Action | Statut |
|--------|--------|
| Choix CPU coherent dans finetune | FAIT — serie par defaut, parallel derriere env guard |
| model_selector.py isole et rendu robuste | FAIT — standalone + integration opt-in dans run_local.py, state runtime hors repo si besoin |
| Remediations MCP dans sous-modules KiCad | FAIT — submodules pointes vers electron-rare, commites |
| crazy_life propre | FAIT — repo clean, CI presente, README versionne (R-005 resolu) |
| Derives docs crazy_life | OUVERT — sync_crazy_life.sh existe, contrat multi-repo non clarifie (R-010) |
| Worktree non melange | OUVERT — encore des fichiers non commites multi-sujets |

### Prochain lot
1. Commiter les fichiers github_dispatch en attente.
2. Decider du sort des fichiers _REAUDIT non suivis.
3. Clarifier le contrat multi-repo (R-010).
4. Clore la boucle de sync locale/canoniques quand `crazy_life`, `Kill_LIFE` et `llmfit` sont alignés.

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

### Avancement: ~99%

| Action | Statut |
|--------|--------|
| Pipeline distill -> merge -> train | FAIT |
| Support CPU + GPU | FAIT |
| Queue GPU + garde-fous VRAM | FAIT |
| --resume fonctionnel | FAIT |
| batch_status.py (distill/train) | FAIT |
| model_selector.py + selected_model.json | FAIT |
| selected_model.json integre dans batch_local.py | FAIT |
| veille web recente integree au workflow de selection | FAIT — `model_selector.py --watch` surveille les releases recentes des auteurs de confiance, ecrit `model_watch_report.json`, puis `run_local.py` / `batch_local.py` la reconsomment automatiquement quand le cache TTL est stale |
| teacher-objective fast/balanced/quality | FAIT |
| scenarios auto_teacher_* dans la matrice | FAIT |
| Teachers local-hf Mistral3/Devstral | FAIT cote Devstral — loader/offline/GPU OK; `iot` (label historique `esp32`), `spice` et `platformio` (`pio`) valides avec auto-teacher `Devstral`; Mistral 3.1 Base sorti du mode auto |
| Reroutage scratch des outputs de training | FAIT — `run_local.py` / `batch_local.py` basculent vers `/dev/shm/mascarade-train` si `models_local/` n a plus assez d espace |
| Export GGUF (4 formats) | FAIT |
| Deploy GGUF vers Ollama | FAIT |
| Scheduler --no-overlap-teacher-train | FAIT — plus de lancement de distill tant qu un train GPU est pret ou actif |
| Batch train=completed | FAIT — mini-batch `iot spice platformio` (labels historiques `esp32 spice pio`) ferme avec `train=completed` sur les 3 domaines |
| Doc operateur --resume | FAIT |
| Benchmark gpu_slots 1 vs 2 | FAIT sur `gpu_24gb_plus` — `Qwen3-4B @1024` training-only: `78.01s` en `1` slot vs `42.01s` en `2` slots, pic VRAM `9.5 Go` vs `17.1 Go` |
| Pre-validation datasets | FAIT — fail-fast + logs IDs normalises + resume court batch + quality gate automatique sur taille/diversite/verbosite dataset + refresh canonique avec brief de recherche web |
| Verification des doublons en fin de workflow | FAIT — refresh canonique, packaging HF et consolidation distill/train dedupent et tracent `duplicates_removed` |
| Racine canonique des modeles | FAIT — tous les scripts/modeles du flux finetuning convergent maintenant vers `/ai/llm` (`huggingface/hub`, `models_cache`, `watch_models`, `apple-llm`), et `~/.cache/huggingface/hub` pointe maintenant dessus |
| Integration modeles dans Mascarade | FAIT — les 10 domaines canoniques sont maintenant promus live: `mascarade-platformio`, `mascarade-stm32`, `mascarade-spice`, `mascarade-iot`, `mascarade-kicad`, `mascarade-freecad`, `mascarade-dsp`, `mascarade-embedded`, `mascarade-power`, `mascarade-emc`; deploy auto via Ollama hote si le store conteneur est RO, scratch `/dev/shm` si le repo FS est plein; les alias publies sont aussi valides via `POST /api/agents/send` |
| Domaine `components` canonique | FAIT — builder canonique, refresh HF, package HF, coverage distributeurs/datasheets/EDA/CAD associee |
| `components` review-ready | FAIT — `merge -> gguf -> deploy -> smoke` valide sur `mascarade-components-review`, promotion live gardee en revue manuelle |
| Benchmark model_selector vs manuel | FAIT — benchmark live HF ferme sur RTX 4090, verdict aligne: `Qwen/Qwen3.5-9B-Base`; artefact: `finetune/runs/model-selector-benchmark-live_20260308_213050/summary.json` |
| Scripts d enchainement auto | FAIT — `scripts/next_finetune_lots.sh` recalcule le prochain lot utile, `scripts/bench_watch_candidate.sh` prepare/execute le benchmark watch, `scripts/auto_chain_next_lots.sh` enchaine automatiquement les prochains lots utiles, `scripts/auto_chain_next_lots_loop.sh` ajoute le mode répétitif (retry bloqué/VRAM), `scripts/migrate_models_to_llm.sh` consolide les caches legacy vers `/ai/llm`. `gpu_preflight` reporté comme blocage propre (`status=blocked`, rc=2) quand `nvidia-smi` indique une indisponibilité (ex: `Failed to initialize NVML`). Rapport vert de reference: `finetune/runs/next-lots_20260309_063107/summary.json` avec `watch_refresh=ok`, `watch_bench=ok`, `prune=ok`, `cad_smoke=ok`, `components_review=ok`. |
| Smoke outillage tmpfs | FAIT — `scripts/cad_tool_smoke_tmpfs.sh` valide maintenant `doctor`, `kicad-cli`, `freecad` et `platformio` dans un workspace tmpfs `/dev/shm/mascarade-cad-smoke/...`; le smoke `kicad_mcp` est trace `unavailable` tant que `finetune/kicad_mcp_server/package.json` est absent, sans casser le lot utile |

### Prochain lot
1. Laisser finir la lane `tuning-party-hf`, puis laisser la boucle deja lancee reprendre automatiquement le benchmark watch `JetBrains/Mellum-4b-*` dans une fenetre GPU libre.
   Etat live: `finetune/runs/auto-next-lots-live_20260309_072329_cycle_1/manifest.json` -> `JetBrains/Mellum-4b-sft-all` actuellement `blocked` (rc=2) tant que la 4090 est occupee.
2. Revue humaine puis `approve` ou rejet de `mascarade-components-review`.
3. Repeupler `finetune/kicad_mcp_server/` ou rediriger la stack vers le vrai serveur KiCad MCP pour faire passer `kicad_mcp` de `unavailable` a `tested`.
4. Executer les autres benchmarks de veille (`Qwen3-Coder-Next-Base`, `DeepSeek-V3.2` teacher-only) via `scripts/auto_chain_next_lots.sh --execute --iterations 1`.
5. Refaire le benchmark slots sur une classe GPU plus contrainte si necessaire.

---

## Axe 6 - VM / Infra

### Avancement: ~45%

| Action | Statut |
|--------|--------|
| Ports en 127.0.0.1 | FAIT |
| Middleware auth implemente | FAIT |
| Auth active (.env rempli) | FAIT — MASCARADE_API_KEY renseignee, routes protegees valides via bearer |
| Rotation Postgres | FAIT |
| CrewAI + OpenAI Agents SDK | FAIT |
| GraphRAG | FAIT |
| Claude Code MCP config VM | FAIT |
| edge-proxy nginx | FAIT — pas de TLS |
| Langfuse ZodError | OUVERT — desactive profile heavy |
| Cles API .env (Anthropic/OpenAI/Notion) | OUVERT |
| Firecrawl | OUVERT |
| Mem0 | PARTIEL — compose migration seulement |
| Docling / Whisper | OUVERT |
| Reverse proxy HTTPS | OUVERT |
| Grafana dashboards | OUVERT |
| Prometheus scrape services | OUVERT |
| Pression memoire (R-001) | OUVERT |
| Faux-verts healthchecks (R-003) | OUVERT |

### Prochain lot
1. Reduire pression memoire/swap (R-001).
2. Corriger faux-verts healthchecks (R-003).
3. Completer les secrets providers encore manquants selon besoin runtime.

---

## Axe 7 - Multi-repo / Kill_LIFE

### Avancement: ~70%

| Action | Statut |
|--------|--------|
| crazy_life propre + CI | FAIT |
| Kill_LIFE 19 workflows CI | FAIT |
| crazy_life synchronise main | FAIT — merge résolu et build web vert |
| Kill_LIFE suivi origine | FAIT — `main...origin/main` |
| llmfit aligned main | FAIT — pull fast-forward `2fd037b..a91feec` |
| Zeroclaw dual HW todo (69/70 items) | FAIT |
| I-205 validation e2e Docker | OUVERT |
| ci_runtime.py / scope_policy.py | ABSENT — references cassees |
| ai-agentic-embedded-base single source | OUVERT — duplique dans Kill_LIFE |
| Contrat multi-repo (R-010) | EN_COURS — contractuel technique prêt à réviser |
| Evidence sync multi-repo | FAIT — [docs/MULTI_REPO_SYNC_STATUS_2026-03-09.md](MULTI_REPO_SYNC_STATUS_2026-03-09.md) |
| CI renforcee (R-011) | PARTIEL |

### Prochain lot
1. Nettoyer les references a ci_runtime.py / scope_policy.py.
2. Valider I-205 (integrations Docker).
3. Verifier le prochain cycle de merge de `crazy_life` sans conflit puis consigner preuve (sha et artefacts).
4. Valider/decider l’usage de `ai-agentic-embedded-base` et documenter le contrat final.

---

## Synthese globale

| Axe | Avancement | Bloqueur principal |
|-----|------------|-------------------|
| 1. Hygiene repo | ~60% | Worktree encore melange, contrat multi-repo |
| 2. CAD / KiCad | ~85% | Smoke TUI, doc OS |
| 3. Cockpit / Obs | ~85% | OTel Collector stub, Grafana, probe GPU |
| 4. OTel / Loki | ~60% | Collector debug-only |
| 5. Fine-tuning | ~99% | Adaptation QLoRA Mellum, puis revue manuelle `components` |
| 6. VM / Infra | ~55% | Pression memoire, healthchecks, secrets providers manquants |
| 7. Multi-repo | ~70% | References cassees, ai-agentic-base |

### Priorite immediate recommandee
1. **VM critique**: reduire pression memoire + fixer healthchecks
2. **Fine-tuning**: adaptation QLoRA Mellum, puis revue `components`
3. **OTel**: remplacer le stub Collector par un vrai exporter
