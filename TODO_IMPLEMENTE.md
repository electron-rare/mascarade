# TODO IMPLEMENTE

Statut suite:
- type: `implemented-reference`
- source active: `docs/EXECUTION_HUB.md`
- regle: conserver ce fichier comme historique livre; tout travail encore vivant doit etre pilote depuis `docs/EXECUTION_HUB.md`

Etat de reference du chantier fine-tuning/distillation local au 6 mars 2026.

## 1. Deja implemente

### RAG — Chunker + URL/file ingestion + Grafana P2P (2026-03-27)
- [x] `rag/chunker.py` : `chunk_text()` / `chunk_document()` — split paragraphe→phrase, merge, overlap, zero deps
- [x] Config : `rag_chunk_size=512`, `rag_chunk_overlap=50`
- [x] `POST /v1/api/rag/ingest` : flag `chunk=true` auto-découpe les docs avant embedding
- [x] `POST /v1/api/rag/ingest/url` : Docling fetch+parse+chunk+embed (PDF, DOCX, HTML…)
- [x] `POST /v1/api/rag/ingest/upload` : Docling upload+chunk+embed, limit 50 MB
- [x] `GET /v1/api/rag/collections` : inclut maintenant vectors_count et points_count par collection
- [x] `GET /v1/api/rag/collections/{name}` : endpoint dédié info collection
- [x] `DELETE /v1/api/rag/collections/{name}` : suppression collection (rag-query-cache protégé)
- [x] `vectorstore.py` : `drop_collection()` + `count()` ajoutés
- [x] `GET /api/cluster/p2p/peers` : liste tous les peers avec gpu_vram_gb, chip_family, ram_gb, connected, total_vram_gb
- [x] `GET /api/cluster/p2p/topology` : nodes incluent maintenant gpu_vram_gb/chip_family/ram_gb
- [x] `scripts/check_docker_user_rules.sh` : vérification/application règles iptables DOCKER-USER (ports 80/3500/5001)
- [x] `deploy/grafana/mascarade-p2p-mesh.json` : dashboard Grafana VRAM gauges, routing skips, mesh peers
- [x] `deploy/edge-proxy` : `cours.saillant.cc` — portail formation HTTP+HTTPS avec redirections LMS + Moodle
- [x] `.env.example` : ajout EDGE_PROXY_LMS/MOODLE/OIDC2FER/COURS server name vars

### CAD Cockpit — crazy_life /cad (2026-03-27)
- [x] Page `/cad` dans crazy_life : status FreeCAD + OpenSCAD runtime, probe KiCad MCP
- [x] Smoke test parallèle (bouton "run smoke test") → tous runtimes en un clic
- [x] Stack reference card (docker profile, MCP port/transport, cad_stack.sh)
- [x] Nav entry Integrations (◈ CAD Stack), route lazy dans App.tsx

### Healthchecks self-hosted (2026-03-27)
- [x] `mascarade-healthchecks` (linuxserver/healthchecks) sur mascarade-postgres (DB `healthchecks`)
- [x] Exposé sur `hc.saillant.cc` — Cloudflare tunnel + DNS CNAME + nginx edge-proxy
- [x] 4 checks câblés : reconnect-api-network (5min), e2e-tests (6h), frappe-backup (24h), pg-backup (24h)
- [x] Scripts ping HC start/success/fail dans reconnect-api-network.sh, run-e2e-notify.sh, pg_backup.sh, frappe-backup.sh
- [x] pg-backup ajouté au crontab (1 0 * * *)

### Node Engine — execution modes + cross-domain (2026-03-27)
- [x] Modes d'exécution : `eager`, `lazy`, `stepped` — API endpoints complets (9/9 ROADMAP)
- [x] 5 adaptateurs cross-domain concrets : AI↔CAD, AI↔Electronics, CAD→Electronics, Electronics→Hardware, Hardware→AI
- [x] HardwareWorker implémenté + Electronics dispatch câblé
- [x] 26 tests API TypeScript passent, 70 tests Python inchangés

### Agentic CLI loop + VRAM metrics (2026-03-27)
- [x] ReAct agentic loop `/agents/{name}/run-agentic` (6 tours max, parse ```tool_call``` blocks)
- [x] `_run_cli_agent_core` partagé entre `/cli-agents/run` et la route agentique
- [x] Gauges Prometheus P2P VRAM : `mascarade_p2p_peer_vram_gb`, `mascarade_p2p_local_vram_gb`, `mascarade_p2p_routing_vram_skips_total`
- [x] Re-announce heartbeat inclut gpu_vram_gb/chip_family/ram_gb
- [x] Lazy env resolution dans servers_registry.py (`"env:VAR_NAME|default"`)

### RAG — Cross-encoder reranking + Contextual Retrieval (2026-03-27)
- [x] `rag/reranker.py` : CrossEncoderReranker (BAAI/bge-reranker-v2-m3), lazy load, thread executor
- [x] Fallback LLM scoring si sentence-transformers absent — zéro régression
- [x] `[reranker]` optional extra dans pyproject.toml
- [x] Config : `rag_reranker_enabled` (défaut True), `rag_reranker_model`
- [x] Contextual Retrieval (pattern Anthropic, -49% failed retrievals) : `pipeline.ingest(contextual_retrieval=True)`
- [x] `_add_contextual_preambles()` : LLM génère un contexte bref par chunk avant embedding

### RAG — Semantic cache + BGE-M3 + Eval (2026-03-27)
- [x] `rag/query_cache.py` : `RAGQueryCache` — Qdrant collection `rag-query-cache` + Redis TTL, seuil cosine 0.92
- [x] Embedding réutilisé sur cache miss (évite double `embed_query`)
- [x] `rag/embeddings.py` : `_embed_ollama()` — BGE-M3 via `{ollama_base_url}/api/embed`, timeout 60s
- [x] Dimensions : bge-m3 → 1024, nomic-embed-text → 768 dans `_MODEL_DIMENSIONS`
- [x] Routing explicite par provider (`ollama`/`openai`/`mistral`) + fallback chain auto
- [x] Config : `rag_embedding_provider`, `rag_embedding_model`, `rag_cache_enabled`, `rag_cache_similarity_threshold`, `rag_cache_ttl`
- [x] `rag/eval.py` : `RAGEvaluator` — 5 métriques RAGAS (faithfulness, answer_relevance, context_precision, context_recall, hallucination_rate)
- [x] LLM judges 4 appels concurrents par item + parse float dans la réponse
- [x] `POST /v1/api/rag/eval` — endpoint FastAPI avec golden dataset et `run_pipeline=True`
- [x] Seuils production : Faithfulness ≥0.85, Answer Relevance ≥0.75, Context Precision ≥0.70, Context Recall ≥0.75, Hallucination <5%

### MCP — data.gouv.fr + edge-proxy oidc2fer (2026-03-27)
- [x] `mcp/server_registry.py` : `register_datagouv_server()` — SSE `https://mcp.data.gouv.fr/sse`, 74k+ datasets publics français
- [x] `mcp/client.py` : branché au `McpRuntimeClient._load_builtin_servers()`
- [x] Opt-out via `DATAGOUV_ENABLED=false`, URL surchargeable via `DATAGOUV_MCP_URL`
- [x] `deploy/edge-proxy/default.conf.template` : blocs nginx `oidc2fer.saillant.cc` (http:80 + https:443) → `http://oidc2fer:8000`

### RAG — Chunker + URL/file ingest + Grafana P2P dashboard (2026-03-27)
- [x] `rag/chunker.py` : `chunk_text()` + `chunk_document()` — paragraph→sentence split, merge à rag_chunk_size tokens, overlap, sans dep externe
- [x] `POST /v1/api/rag/ingest` : param `chunk=true` + `contextual_retrieval` passthrough
- [x] `POST /v1/api/rag/ingest/url` : Docling fetch → chunk → embed → upsert, OCR opt-in
- [x] `POST /v1/api/rag/ingest/upload` : file upload → Docling parse → chunk → embed → upsert, limite 50MB
- [x] Config : `rag_chunk_size=512`, `rag_chunk_overlap=50`
- [x] Grafana `mascarade-p2p-mesh.json` : Peer VRAM timeseries, Local VRAM stat, Peers Online, Routing Skips/min, Peer Up/Down state timeline
- [x] `edge-proxy` : vhost `cours.saillant.cc` — portail HTML LMS/Moodle, HTTP→HTTPS redirect

### Fine-tuning — Phase B/C/D scripts (2026-03-27)
- [x] `finetune/batch_phase_b.sh` : rejection sampling 10 domaines, N_CANDIDATES=8, output `dpo_pairs/{domain}/`
- [x] `finetune/batch_phase_c.sh` : ORPO training (pas de reference model, −3GB VRAM), détecte dernier adapteur Phase A
- [x] `finetune/batch_phase_d.sh` : merge → GGUF → Ollama + HF upload `clemsail/mascarade-{domain}-lora` avec model card
- [x] `finetune/batch_phases_bcd.sh` : chaîne B→C→D, option `--skip-phase-d`
- [x] `TODO_TUNNING_PARTY.md` mis à jour avec références scripts

### La Suite Numérique (2026-03-26)
- [x] Stack déployée : conversations (:8082), impress/docs (:8073), keycloak (:8085)
- [x] S3 consolidé sur `mascarade-langfuse-minio` — buckets `conversations-media-storage` + `impress-media-storage`
- [x] OIDC branché sur `auth.saillant.cc/realms/zacus` (clients conversations + impress déjà configurés)
- [x] Keycloak healthcheck bash TCP (pas de curl dans l'image)
- [x] Cloudflare tunnel : `conversations.saillant.cc → :8082`, `docs.saillant.cc → :8073`
- [x] DNS CNAMEs créés et proxifiés CF
- [x] Git : `electron-rare/suite-numerique` (privé), forks suitenumerique (conversations, docs, meet, people, find)
- [x] MCP Outline activé — `OUTLINE_API_KEY` dans `.env`

### Mesh P2P hardware-aware (2026-03-26)
- [x] Registre VRAM par modèle Ollama — `router/model_sizes.py` (lookup exact + heuristique param-count)
- [x] `PeerCapabilities` étendu : `gpu_vram_gb`, `chip_family`, `ram_gb` gossipés via PubSub + DHT
- [x] `NodeIdentity` injecte `detect_machine_profile()` au démarrage du cluster
- [x] `select_route()` filtre les pairs par VRAM, désactive local si trop petit pour le modèle
- [x] `P2PProvider._resolve_peer()` préfère les pairs VRAM-capables (tri desc)
- [x] `OllamaProvider._ensure_model()` / `_pull_model()` — auto-pull avant la première requête
- [x] Résultat : Tower (5GB) garde les petits modèles ; KXKM-AI (RTX 4090 24GB) reçoit les gros

### Pipeline local
- [x] Point d'entree unique pour lancer le fine-tuning local CPU/GPU
- [x] Support `LoRA/QLoRA` local avec `venv_tuning`
- [x] Fallback CPU utilisable quand CUDA est indisponible
- [x] Smoke tests reels valides en CPU et en GPU
- [x] Politique de defaults coherente:
  - GPU / student principal = `Qwen/Qwen2.5-Coder-1.5B-Instruct`
  - CPU fallback = `TinyLlama/TinyLlama-1.1B-Chat-v1.0`

### Distillation teacher -> student
- [x] Pipeline complet `distill -> merge -> train`
- [x] Support teacher via API locale sur `http://127.0.0.1:8100`
- [x] Support `mistral` comme teacher principal
- [x] Mode JSON strict cote teacher Mistral
- [x] Retries sur JSON invalide et erreurs reseau/transitoires
- [x] Rapport de distillation JSON avec succes/echecs
- [x] Export optionnel des rows en echec

### Robustesse du routeur
- [x] Requetes teacher strictes sans fallback silencieux vers `bedrock`
- [x] Garde-fou si le provider retourne autre chose que celui demande
- [x] Cache evite sur les requetes strictes cross-provider
- [x] Timeout Mistral allonge pour les gros prompts

### Verbosite et suivi
- [x] Flags `--verbose` et `--quiet`
- [x] Progress bars cote tokenization/training
- [x] Logs plus lisibles cote distillation
- [x] Scripts de debug pour le core local sur `8100`

### Parallellisation du pipeline
- [x] Concurrence configurable pour la distillation teacher
- [x] Tokenization multi-workers cote training
- [x] Orchestrateur batch multi-domaines ajoute
- [x] Aliases de domaines:
  - `esp32 -> iot`
  - `pio -> platformio`
- [x] Manifest d'execution par run batch
- [x] Reprise `--resume` sur le batch
- [x] Queue GPU avec limite de trainings paralleles
- [x] Garde-fou VRAM avant lancement d'un second training GPU
- [x] Wrapper shell pour lancer le batch multi-domaines

## 2. Scripts et entrees disponibles

- [x] `finetune/run_local.py`
- [x] `finetune/distill_dataset.py`
- [x] `finetune/distill_and_train.py`
- [x] `finetune/batch_local.py`
- [x] `finetune/batch_status.py`
- [x] `finetune/model_selector.py` (experimental, non branche au pipeline)
- [x] `scripts/finetune_local.sh`
- [x] `scripts/distill_and_train.sh`
- [x] `scripts/parallel_domains_gpu_queue.sh`
- [x] `scripts/debug_core_8100.sh`
- [x] `scripts/debug_mistral_smoke.sh`

## 3. Etat reel du batch parallele

### Ce qui passe deja
- [x] `kicad` valide en distillation Mistral + training GPU local
- [x] `spice` passe sur le chemin distill + merge en smoke test batch
- [x] `platformio` passe sur le chemin distill + merge en smoke test batch
- [x] `esp32` alias `iot` passe maintenant sur le chemin distill + merge en smoke test batch
- [x] Le dataset source `iot` est valide apres normalisation `ensure_row_ids()`

### Verifie par audit (7 mars 2026)
- [x] `--resume` fonctionne: `load_resume_manifest()`, skip des domaines completed
- [x] `batch_status.py` distingue correctement `distill` et `train` par domaine
- [x] `selected_model.json` lu par `run_local.py` au boot via `resolve_model()`
- [x] Export GGUF complet dans `pipeline.py`: q4_k_m, q4_k_s, q5_k_m, q8_0
- [x] Deploy GGUF vers Ollama dans `pipeline.py`: docker cp/exec + test inference
- [x] `auto_chain_next_lots.sh` continue avec fallback `selected_model.json` si le watch report est temporairement indisponible et reste en mode `--continue-on-error`.

### Ce qui reste a verrouiller
- [x] Valider la phase `train` de bout en bout sur un run batch `esp32 spice pio`
- [x] Documenter la reprise `--resume` dans la doc operateur (code OK, doc manquante)
- [x] Mesurer si `2` trainings GPU paralleles apportent un gain reel sur Quadro P2000 — benchmark RTX 4090: slots=1→78s, slots=2→42s, speedup 1.857x (cf. `TODO_TUNNING_PARTY.md`)
- [x] Robustifier `auto_chain_next_lots_loop.sh` : backoff adaptatif sur `blocked` et interdiction de `--report-dir` en pass-through.

### Verification au 6 mars 2026
- [x] `finetune/runs/smoke_batch_20260306_191758`: `esp32`, `spice`, `pio` en `distill=completed`
- [x] `finetune/runs/smoke_batch_gpu_20260306_193427`: `esp32`, `spice`, `pio` en `distill=completed`
- [x] `finetune/runs/smoke_batch_gpu2_20260306_195107`: `esp32`, `spice`, `pio` en `distill=completed`
- [x] Les manifests ci-dessus sont passés en `train=completed` après reprise batch (validation consolidée dans le plan d'execution actuel).
- [x] Tentative auto-lot `Mellum` réalisée: `finetune/runs/auto-next-lots_20260309_071455/manifest.json` (`status=blocked`, `runs_blocked=1`) en attendant fin `tuning-party-hf`.

## 4. TODO Agent Zero

Objectif: cadrer si `Agent Zero` doit rester un sujet d'etude, un outil de debug, ou une vraie brique d'orchestration dans Mascarade.

- [x] Identifier precisement le perimetre `Agent Zero` vise ici
  - Cadrage fait le 2026-03-23: 3 tiers identifies (copilot, orchestration, batch)
- [x] Comparer `Agent Zero` avec l'orchestrateur local deja implemente dans `finetune/batch_local.py`
  - Conclusion: complementaires, pas concurrents. Agent Zero = decision support, Batch = execution pipeline
- [x] Definir si `Agent Zero` sert a:
  - Tier 1 (implemente): operator copilot — analyse incidents/logs, propose next action manuelle
  - Tier 2 (design): orchestration initiator — decompose demande → selectionne template → lance agents
  - Tier 3 (exploratoire): batch coordination — supervise fine-tuning (read-only, approval-gated)
- [x] Faire un POC isole, sans melanger tout de suite la chaine de fine-tuning existante
  - Endpoint `/v1/api/agents/agent-zero/copilot` implemente (commit `ef07b5b`)
  - Isole du pipeline fine-tuning, read-only
- [x] Evaluer le cout de maintenance avant integration repo
  - Cout faible: ~110 lignes dans routers/agents.py + 1 param dans base.py
- [x] Definir les garde-fous:
  - isolation des secrets: redaction automatique (_redact_secrets) avant envoi LLM
  - limites CPU/GPU: CPU-only inference, routing_policy=strong, pas de GPU
  - timeout des jobs: max_tokens=4096, temperature=0.2
  - logs et reprise: trace complete via AgentTraceBuffer existant

## 5. Prochain ordre de travail recommande

1. Relancer `./scripts/auto_chain_next_lots.sh --execute --iterations 1 --continue-on-error` dès libération GPU (dernier run bloqué: `auto-next-lots_20260309_071455`).
   - alternative enchaînée: `./scripts/auto_chain_next_lots_loop.sh --iterations 1 --sleep-seconds 20 --max-cycles 3 --max-blocked-streak 10`
     - preuve: `finetune/runs/auto-next-lots_20260309_071721_cycle_1/manifest.json`, `...071741_cycle_2/manifest.json`, `...071801_cycle_3/manifest.json`.
   - preuve: `finetune/runs/auto-next-lots_20260309_071539_cycle_1/manifest.json` (`runs_blocked=1`).
2. Mesurer le gain réel de `2` trainings GPU parallèles sur RTX 4090.
3. Verrouiller le contrat `R-010` multi-repo avec preuves de sync `crazy_life` / `Kill_LIFE` / `llmfit`.
4. Revoir la place d'`Agent Zero` hors pipeline critique (expérimentation isolée).

## 6. Cockpit frontend deja implemente

### Shell et navigation
- [x] Shell React unifie avec sidebar desktop, drawer mobile et mobile dock
- [x] Raccourcis clavier `Alt+1..9`
- [x] Panneau session/auth clavier-safe
- [x] Fond visuel Matrix/CRT conserve comme direction par defaut

### Pages cockpit
- [x] Refonte `Dashboard`
- [x] Refonte `Playground`
- [x] Refonte `Agents`
- [x] Refonte `Agent Detail`
- [x] Refonte `Orchestrate`
- [x] Refonte `Metrics`
- [x] Refonte `Infrastructure`
- [x] Refonte `Notion Browser`
- [x] Refonte `ComfyUI`
- [x] Lane `Logs` ajoutee au cockpit

### Agent Zero
- [x] `agent-zero` ajoute comme agent builtin dans le core
- [x] `agent-zero` expose visiblement dans le cockpit
- [x] `agent-zero` mis en avant dans `Dashboard`, `Agents`, `Agent Detail`, `Orchestrate`
- [x] CTA de cadrage incident vers `agent-zero` ajoutes dans les surfaces ops

## 7. Observability deja implemente

### Trace native Mascarade
- [x] `run_id` stable sur les runs d'orchestration
- [x] Evenements inter-agent structures dans le core
- [x] Buffer recent de traces dans le core
- [x] Exposition des traces via routes core dediees

### Facade ops API
- [x] `GET /api/ops/monitor`
- [x] `GET /api/ops/summary`
- [x] `GET /api/ops/sources`
- [x] `GET /api/ops/logs/recent`
- [x] `GET /api/ops/agent-traces/recent`
- [x] `GET /api/ops/agent-traces/:runId`

### Surface cockpit
- [x] Vue `Logs` pour lire incidents services + traces inter-agent
- [x] Panneau `live run trace` dans `Orchestrate`
- [x] Liens directs vers `Logs` depuis `Dashboard`, `Metrics`, `Infrastructure`

### Infra complementaire scaffolded
- [x] Modules `loki`, `promtail`, `otel-collector`
- [x] Configs `deploy/loki`, `deploy/promtail`, `deploy/otel-collector`
- [x] Spec produit cockpit dans `docs/FRONTEND_SPEC.md`
- [x] Spec technique observability dans `docs/OBSERVABILITY_ARCHITECTURE.md`

## 8. Backlogs actifs a suivre

- [x] Backlog fine-tuning detaille dans `TODO_TUNNING_PARTY.md`
- [x] Backlog cockpit/ops detaille dans `TODO_COCKPIT_OPS.md`

## 9. CAD / KiCad deja implemente

### Structure repo
- [x] Repositories KiCad enregistres comme sous-modules
- [x] Sous-module legacy `vendors/kicadrouterai` remappe proprement dans `.gitmodules`

### Helpers versionnes
- [x] `scripts/install_kicad_plugins.sh list`
- [x] `scripts/install_kicad_plugins.sh plugin-dir`
- [x] `scripts/install_kicad_plugins.sh install`
- [x] `scripts/install_kicad_plugins.sh doctor`
- [x] `scripts/cad_stack.sh up|down|ps|doctor|mcp`

### Ce qui reste a faire
- [x] Integrer la section `CAD / KiCad` dans `./config`
- [x] Ajouter les actions `--cad-plugins`, `--cad-doctor`, `--cad-stack` dans `./setup`
- [x] Consolider la doc operateur CAD/TUI
