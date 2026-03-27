# RAG & Gestion Documentaire — État de l'Art Mars 2026

> Date: 2026-03-26 | Auteur: Claude Sonnet 4.6 + Clems | Sources: 50+ références

---

## 1. Techniques RAG — Évolution 2026

Le RAG "naïf" (retrieve-then-generate linéaire) est considéré **obsolète** en 2026. Les architectures modernes sont des boucles agentiques.

### 1.1 Hiérarchie des approches (du plus simple au plus avancé)

| Approche | Gain vs baseline | Coût implémentation | Recommandation |
|---|---|---|---|
| **Hybrid search** (dense + BM25) | +15–25% recall | Faible | ✅ Standard production |
| **Contextual Retrieval** (Anthropic) | -49 à -67% failed retrievals | Moyen | ✅ ROI exceptionnel |
| **Cross-encoder reranking** | +10–30% précision | Faible (lib) | ✅ Systématique |
| **HyDE** | +recall sur queries courtes | Faible | ⚠️ Si queries abstraites |
| **CRAG** | Corrige mauvais retrievals | Moyen | ✅ Déjà dans mascarade |
| **Self-RAG** | -25–40% retrievals inutiles | Élevé (fine-tuning) | ⏳ Futur |
| **Agentic RAG** | Qualité maximale | Élevé | ✅ En cours mascarade |
| **GraphRAG** | +10% relational QA | Très élevé | ⏳ Si corpus >5k docs |
| **ColPali** | Révolutionnaire sur PDFs visuels | Moyen | ⚠️ Si docs visuellement riches |

### 1.2 Contextual Retrieval (Anthropic — meilleur ROI immédiat)

Avant indexation, un LLM génère un préambule contextuel pour chaque chunk.
- **-49%** failed retrievals (embeddings seuls)
- **-67%** combiné avec reranking
- Coût : ~1 token input supplémentaire/chunk à l'indexation (utiliser claude-haiku)

### 1.3 GraphRAG — Comparatif

| | Microsoft GraphRAG | LightRAG | Cognee |
|--|---|---|---|
| Concept | Community detection + summaries hiérarchiques | Dual-level (local + global) | Memory engine : graph + vector |
| Coût tokens | Très élevé | **10x moins** que GraphRAG | Modéré |
| Latence | ~120ms+ | **~80ms** | Variable |
| Cas d'usage | Corpus très relationnel >5k docs | Production cost-sensitive | Agents mémoire longue durée |
| Open-source | MIT | MIT | Apache 2 |

**Recommandation** : LightRAG si besoin (65–80% d'économies tokens vs MS GraphRAG).

### 1.4 ColPali / Vision RAG (révolutionnaire)

Traite les pages PDF directement comme **images** — pas de parsing, OCR, chunking.
- **Nemotron ColEmbed V2** (NVIDIA, fév. 2026) : #1 ViDoRe V3 — NDCG@10 **63.42**
- ColQwen2-VL (2B) : +5.3 nDCG@5 vs ColPali original
- Surpasse largement les pipelines Unstructured + captioning sur docs visuellement complexes

**Quand l'utiliser** : PDFs avec schémas, graphiques, tableaux complexes (datasheets KXKM !)

---

## 2. Benchmarks et Évaluation

### 2.1 RAGAS v0.4 — Métriques production

| Métrique | Seuil production | Description |
|---|---|---|
| Faithfulness | ≥ 0.85 | Claims soutenus par le contexte |
| Answer Relevance | ≥ 0.75 | La réponse répond-elle à la question ? |
| Context Precision | ≥ 0.70 | Chunks pertinents bien rankés |
| Context Recall | ≥ 0.75 | Toute l'info nécessaire récupérée |
| Hallucination Rate | < 5% | Réponses non supportées |

Coût : ~$0.001–0.003/cas de test avec GPT-4o-mini.

### 2.2 Insight clé

> "La précision du retrieval explique seulement 60% de la variance de la qualité RAG end-to-end. Les 40% restants viennent de la génération."

---

## 3. Vector Stores — Comparatif Mars 2026

| | Qdrant | pgvector+pgvectorscale | Weaviate | Pinecone |
|--|---|---|---|---|
| Licence | Apache 2 | PostgreSQL | BSD-3 | Propriétaire |
| Hybrid search | ✅ natif v1.9+ | ❌ dense seulement | ✅ WAND | ✅ |
| GPU accel | ❌ | ❌ | ❌ | ❌ |
| Self-host | ✅ | ✅ (PostgreSQL) | ✅ | ❌ |
| Perf 50M vecteurs | 41.47 QPS / 22ms p95 | **471 QPS** (StreamingDiskANN) | Variable | <10ms (managed) |
| Meilleur pour | Filtres complexes, self-host | Stack Postgres existant | Enterprise multimodal | Turnkey |

**Surprise** : pgvectorscale surpasse Qdrant de **11.4x** à 99% recall sur 50M vecteurs. Mais Qdrant reste supérieur sur filtres complexes et souveraineté.

---

## 4. Embedding Models — MTEB Mars 2026

| Modèle | Type | MTEB | Dims | Recommandation |
|---|---|---|---|---|
| **BGE-M3** | Open-source | 63.0 | 1024 | ✅ Production self-hosted — dense + sparse + multi-vector |
| **Qwen3-Embedding-8B** | Open-source | 70.58 | 4096 | 🔥 SOTA si GPU dispo |
| **nomic-embed-text** | Open-source/Ollama | ~62 | 768 | ✅ Local via Ollama (déjà dans mascarade) |
| **Voyage-3-large** | API | 66.80 | 2048 | ✅ Meilleur rapport qualité/prix API ($0.06/M) |
| **text-embedding-3-small** | API OpenAI | 62.26 | 1536 | ✅ Déjà configuré mascarade |
| **mistral-embed** | API | ~60 | 1024 | ✅ Déjà configuré mascarade |

**Recommandation upgrade** : passer de `nomic-embed-text` à **BGE-M3** pour le hybrid search natif (produit dense + sparse en un seul modèle).

---

## 5. Document Parsing — Comparatif

| Outil | Tables complexes | OCR | Vitesse | Coût | Self-host |
|---|---|---|---|---|---|
| **Docling** (IBM) | **97.9%** | ✅ | 28ms/page (A100) | Gratuit | ✅ MIT |
| **LlamaParse v2** | Bien | ✅ agentic | ~6s/doc | $1.25/1000 crédits | ❌ |
| **Mistral OCR** | Bien multicolonne | ✅ + manuscrit | Rapide | API | ❌ |
| **Unstructured.io** | 75% | ✅ | Bon | $1–10/1000p | ✅ (qualité réduite) |

**Verdict sur Docling** : meilleur en self-hosted pour tables complexes. Mais nécessite ~1-2 GB RAM et aucun consommateur actif dans mascarade → gardé désactivé jusqu'à pipeline datasheet réel.

**Alternative zero-infra** : **Mistral OCR** via API pour les besoins ponctuels.

---

## 6. Gestion Documentaire — Stack Recommandée

### 6.1 Knowledge bases comparatif

| Outil | AI native | Self-host | Ollama | Usage recommandé |
|---|---|---|---|---|
| **Outline** | AI Answers (beta) | ✅ BSD-3 | Partiel | ✅ Wiki équipe — déjà dans mascarade |
| **Obsidian** | Via plugins (2700+) | ✅ local-first | ✅ direct | PKM personnel |
| **Notion AI 3.0** | ✅ agentique | ❌ cloud | ❌ | Équipes cloud |
| **Karakeep** | Auto-tagging + summary | ✅ Docker | ✅ Ollama | Bookmarks AI (phase2) |
| **Paperless-ngx** | Via paperless-gpt | ✅ Docker | ✅ LLaVA | Archives docs scannés |

### 6.2 RAG clé-en-main self-hosted

| Outil | Stars | Description | Verdict |
|---|---|---|---|
| **RAGFlow** | +35k | DMS + RAG + GraphRAG + multimodal, workflow visuel | 🔥 À surveiller |
| **AnythingLLM** | +35k | Upload + RAG + chat, 50+ formats, Ollama | ✅ Simple, efficace |
| **Danswer/Onyx** | +13k | Enterprise search, connecteurs Confluence/Slack | ✅ Si multi-sources |
| **Morphik** | Croissant | Multimodal RAG (charts, PDFs), SQL + PDF | ⏳ Émergent |

### 6.3 Multiformat — Ingestion par type

| Format | Outil recommandé |
|---|---|
| PDF texte | Docling ou Mistral OCR (API) |
| PDF visuel (schémas, graphiques) | ColPali/ColQwen2 ou Nemotron ColEmbed V2 |
| DOCX/PPTX/XLSX | MarkItDown (Microsoft, gratuit, local) |
| Images scannées | LLaVA via Ollama (LLM-OCR) |
| KiCad (.kicad_sch/.kicad_pcb) | Parser custom S-expressions → Markdown/JSON par composant/net |
| HTML/Web | Crawl4AI (open-source) |
| Audio | faster-whisper (déjà dans mascarade) |
| Code | Tree-sitter + LlamaIndex |

**KiCad spécifique** : [`jasiek/kicad-llm-plugin`](https://github.com/jasiek/kicad-llm-plugin) existe. Les fichiers `.kicad_sch` sont du texte S-expressions → parsing `sexpdata` Python → chunks par composant/net → Qdrant.

---

## 7. Analyse Gaps — Mascarade RAG vs SOTA 2026

### 7.1 Ce qui existe déjà ✅

- Hybrid search (dense + BM25 + RRF) — Qdrant v1.9+
- CRAG fallback (score < 0.3 → SearXNG)
- Multi-source routing (Qdrant / MCP / Memory / Web)
- LLM-based reranking (simulation cross-encoder)
- Multi-provider embeddings avec fallback chain
- Document chunking avec overlap
- Intent classification

### 7.2 Gaps critiques ❌

| Gap | Impact | Effort | Priorité |
|---|---|---|---|
| **True cross-encoder reranking** (BGE-Reranker ou Cohere) | +10–30% précision | Faible | P0 |
| **Contextual Retrieval** (Anthropic pattern) | -49–67% failed retrievals | Moyen | P0 |
| **Evaluation RAGAS** | Mesurabilité | Faible | P1 |
| **Query expansion / HyDE** | +recall queries courtes | Moyen | P1 |
| **BGE-M3 embedding** (dense+sparse unifié) | Hybrid search natif | Faible | P1 |
| **Semantic query cache** | -50–70% coût LLM | Moyen | P1 |
| **GraphRAG / LightRAG** | Relations entre entités | Élevé | P2 |
| **ColPali** (vision RAG) | PDFs schémas techniques | Élevé | P2 |
| **Pipeline ingestion docs** | Base de connaissances | Moyen | P2 |

### 7.3 Stack cible recommandée (évolution mascarade)

```
PARSING    : Docling (tables) + Mistral OCR (scans) + MarkItDown (Office)
CHUNKING   : Hierarchical + Contextual Retrieval (LLM préambule/chunk)
EMBEDDING  : BGE-M3 (dense+sparse, self-hosted) — remplace nomic-embed
VECTORSTORE: Qdrant (déjà là) — activer Qdrant sparse vectors pour BM25 natif
RETRIEVAL  : Hybrid search (déjà là) — pondération 75% dense / 25% sparse
RERANKING  : BGE-Reranker-v2-m3 (self-hosted) — remplace LLM simulation
EVALUATION : RAGAS v0.4 — golden dataset 50–200 questions
GRAPH      : LightRAG (si corpus >1k docs, cost-effective)
```

---

## 8. Papers Clés (arXiv 2025-2026)

| Date | Paper | arXiv | Contribution |
|---|---|---|---|
| Jan 2026 | Agentic RAG Survey | [2501.09136](https://arxiv.org/abs/2501.09136) | Survey complet |
| Fév 2026 | A-RAG: Hierarchical Retrieval Interfaces | [2602.03442](https://arxiv.org/abs/2602.03442) | Hierarchical tool-use agents |
| Fév 2026 | Nemotron ColEmbed V2 | [2602.03992](https://arxiv.org/abs/2602.03992) | SOTA visual document retrieval |
| Fév 2026 | SPARC-RAG | [2602.00083](https://arxiv.org/abs/2602.00083) | Multi-agent sequential-parallel |
| Fév 2026 | SF-RAG | [2602.13647](https://arxiv.org/html/2602.13647v2) | Structure-fidelity sur docs académiques |
| Jan 2026 | ManuRAG | [2601.15434](https://arxiv.org/pdf/2601.15434) | RAG multimodal docs manufacturiers |
| Oct 2024 | RAG Survey comprehensive | [2410.12837](https://arxiv.org/abs/2410.12837) | Référence 2025 |

---

## 9. Recommandations Actions Immédiates

### P0 — Quick wins (faible effort, fort impact)

1. **Passer au vrai cross-encoder** : remplacer la simulation LLM par `BAAI/bge-reranker-v2-m3` via sentence-transformers — API identique, +10–30% précision, moins coûteux
2. **Contextual Retrieval à l'indexation** : ajouter un préambule LLM (haiku) pour chaque chunk avant embedding — -49% failed retrievals

### P1 — Sprint suivant

3. **BGE-M3 comme modèle d'embedding** : remplace nomic-embed-text, produit dense + sparse en un appel, améliore le hybrid search natif Qdrant
4. **RAGAS golden dataset** : créer 50 questions de référence sur le corpus existant, mesurer baseline
5. **Semantic query cache** (Redis) : évite les re-embeddings sur requêtes similaires

### P2 — Roadmap

6. **Pipeline ingestion KiCad** : parser `.kicad_sch` → chunks composants → Qdrant → RAG sur schémas
7. **ColPali** : pour les datasheets PDF JLCPCB/LCSC — vision directe, zéro parsing
8. **LightRAG** : si le corpus Outline/Qdrant dépasse 1k documents

---

*Sources : 50+ références incluant arxiv.org, anthropic.com, huggingface.co, MTEB leaderboard, ViDoRe V3, GitHub repositories*
