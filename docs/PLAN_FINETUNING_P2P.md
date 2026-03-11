# Plan — Fine-tuning distribué P2P

## Vision

Système multi-agent de fine-tuning distribué sur le mesh P2P mascarade.
Chaque nœud joue un rôle spécialisé. La recherche de modèles/datasets,
l'entraînement, la validation et l'optimisation sont partagés en P2P.

---

## Architecture agents

### 8 rôles spécialisés

| Agent | Rôle | Capability P2P | Nœud idéal |
|-------|------|----------------|------------|
| **Chercheur** | Recherche web de modèles (HuggingFace, Papers) | `ft-research` | Local (internet) |
| **Documentaliste** | Recherche et curation de datasets | `ft-dataset` | Local (internet) |
| **Archiviste** | Versioning modèles/datasets, registre HF | `ft-archive` | VM (storage) |
| **Analyste** | Évaluation benchmarks, métriques qualité | `ft-analysis` | Local (compute) |
| **Doctor** (teacher) | Génère données d'entraînement (Claude/GPT) | `ft-teacher` | Local (API keys) |
| **Student** | Entraîne le modèle local (LoRA/QLoRA) | `ft-student` | VM (compute) ou Local (Metal) |
| **Renforceur** | DPO/RLHF, amélioration itérative | `ft-reinforcement` | Local (compute) |
| **Validateur** | Tests e2e, red-teaming, certification | `ft-validation` | CILS (indépendant) |

### Flux

```
Chercheur → trouve base model + papers
     ↓
Documentaliste → trouve/crée dataset
     ↓
Doctor → génère teacher data (Claude)
     ↓
Archiviste → versionne sur HuggingFace
     ↓
Student → fine-tune LoRA (local ou VM)
     ↓
Analyste → benchmarks + métriques
     ↓
Renforceur → DPO sur erreurs détectées
     ↓
Validateur → tests e2e + red-team
     ↓
Archiviste → publie modèle final
```

---

## Phase 1 — Recherche automatique (semaine 1)

### 1.1 Agent Chercheur (`ft-research`)
- Utilise HuggingFace Hub API pour chercher modèles par:
  - Tâche (text-generation, code, embeddings)
  - Taille (< 3B pour local, < 7B pour VM)
  - License (Apache 2.0, MIT)
  - Popularité (downloads, likes)
- Utilise arXiv/Papers pour trouver techniques récentes
- Produit un rapport: `{model_id, size, quantization, benchmark_scores, paper_refs}`

### 1.2 Agent Documentaliste (`ft-dataset`)
- Cherche datasets HuggingFace par domaine
- Vérifie qualité: taille, format, license, langues
- Crée datasets synthétiques si besoin (via Doctor)
- Produit: `{dataset_id, size, format, splits, quality_score}`

### Implémentation
```python
# mascarade/finetune/agents/researcher.py
class ResearcherAgent:
    """Cherche modèles et papers via HuggingFace Hub + arXiv."""

    async def search_base_models(self, task: str, max_size_gb: float = 4.0):
        # hub_repo_search(query=task, type="model", sort="downloads")
        # Filtrer par taille, license, quantization dispo
        pass

    async def search_papers(self, topic: str):
        # paper_search(query=topic)
        pass

# mascarade/finetune/agents/documentalist.py
class DocumentalistAgent:
    """Cherche et curate datasets."""

    async def search_datasets(self, domain: str, min_rows: int = 1000):
        # hub_repo_search(query=domain, type="dataset")
        pass

    async def create_synthetic_dataset(self, spec: dict):
        # Utilise Doctor (Claude) pour générer
        pass
```

---

## Phase 2 — Génération teacher data (semaine 1-2)

### 2.1 Agent Doctor (`ft-teacher`)
- Prend un dataset brut + spec de tâche
- Utilise Claude (via mascarade Router, strategy=BEST) pour générer:
  - Paires instruction/response de haute qualité
  - Corrections d'erreurs détectées
  - Augmentation de données
- Format output: JSONL compatible `trl` / `axolotl`

### 2.2 Agent Archiviste (`ft-archive`)
- Versionne chaque artefact sur HuggingFace:
  - Datasets: `clemsail/mascarade-{domain}-v{n}`
  - Modèles: `clemsail/mascarade-{task}-{size}-v{n}`
  - Métriques: dans les model cards
- Gère le registre local `~/.mascarade/finetune/registry.json`

---

## Phase 3 — Entraînement distribué (semaine 2-3)

### 3.1 Agent Student (`ft-student`)
- Charge le base model + dataset depuis l'Archiviste
- Fine-tune avec LoRA/QLoRA:
  - Sur VM: CPU-only (petit modèle, qwen2.5:0.5b)
  - Sur Local (GrosMac): Metal/MPS pour modèles jusqu'à 7B
  - Sur CILS: CPU backup
- Export en GGUF pour llama.cpp
- Publie résultats vers Analyste

### 3.2 Pipeline technique
```
Base model (GGUF/safetensors)
    → LoRA adapter training (trl/peft ou llama.cpp finetune)
    → Merge adapter → full model
    → Quantize GGUF (Q4_K_M)
    → Deploy sur llama-server local
    → Register dans mascarade comme provider
```

### Distribution P2P
- Task `ft-student` distribuée via `node.distribute_task()`
- Le nœud avec `ft-student` capability claim la tâche
- Payload: `{base_model, dataset_url, lora_config, output_repo}`
- Result: `{model_url, metrics, training_time}`

---

## Phase 4 — Évaluation et renforcement (semaine 3)

### 4.1 Agent Analyste (`ft-analysis`)
- Benchmarks automatiques:
  - Perplexité sur test set
  - Accuracy sur tâches spécifiques (code, kicad, etc.)
  - Vitesse d'inférence (tokens/s)
  - Taille mémoire
- Compare student vs teacher vs baseline
- Produit rapport de qualité

### 4.2 Agent Renforceur (`ft-reinforcement`)
- Collecte les erreurs détectées par Analyste
- Génère paires DPO (chosen/rejected) via Doctor
- Relance un cycle Student avec les données DPO
- Itère jusqu'à convergence qualité

### 4.3 Agent Validateur (`ft-validation`)
- Tourne sur CILS (nœud indépendant, pas d'influence)
- Tests:
  - Red-teaming: prompts adversariaux
  - Regression: compare avec version précédente
  - Domain-specific: KiCad validation, compliance, etc.
  - Safety: refuse les prompts dangereux
- Donne le GO/NO-GO pour publication

---

## Phase 5 — Intégration mascarade (semaine 3-4)

### Auto-registration provider
- Le modèle validé est automatiquement:
  1. Déployé sur llama-server (port configurable)
  2. Enregistré comme provider mascarade
  3. Annoncé sur le mesh P2P avec capability `llm-finetuned-{domain}`
- Le Router peut alors l'utiliser via:
  - `strategy=CHEAPEST` → local fine-tuné (gratuit)
  - `strategy=BEST` → Claude (qualité max)

### Cycle continu
- Chaque semaine, le Chercheur vérifie les nouveaux modèles/datasets
- Le Doctor génère de nouvelles données à partir des logs d'utilisation
- Le Student re-fine-tune avec les données accumulées
- Le Validateur certifie avant promotion en production

---

## Fichiers à créer

```
mascarade/finetune/
├── agents/
│   ├── __init__.py
│   ├── researcher.py      # Chercheur — recherche modèles/papers
│   ├── documentalist.py   # Documentaliste — datasets
│   ├── archivist.py       # Archiviste — versioning HF
│   ├── analyst.py         # Analyste — benchmarks
│   ├── teacher.py         # Doctor — génération data
│   ├── student.py         # Student — fine-tuning
│   ├── reinforcer.py      # Renforceur — DPO/RLHF
│   └── validator.py       # Validateur — tests e2e
├── p2p/
│   ├── __init__.py
│   ├── capabilities.py    # P2P capabilities pour fine-tuning
│   └── task_handlers.py   # Handlers distribués
├── registry.py            # Registre local modèles/datasets
└── orchestrator.py        # Orchestre le pipeline complet
```

---

## Capabilities P2P

```python
FT_CAPABILITIES = {
    "ft-research": "Recherche modèles et papers",
    "ft-dataset": "Recherche et curation datasets",
    "ft-archive": "Versioning HuggingFace",
    "ft-analysis": "Benchmarks et métriques",
    "ft-teacher": "Génération teacher data (nécessite API keys)",
    "ft-student": "Fine-tuning LoRA (nécessite GPU/Metal ou CPU)",
    "ft-reinforcement": "DPO/RLHF amélioration",
    "ft-validation": "Tests e2e et red-teaming",
}
```

---

## Priorités

| # | Action | Effort | Dépend de |
|---|--------|--------|-----------|
| 1 | Agent Chercheur (HF search) | 2h | HuggingFace MCP |
| 2 | Agent Documentaliste (dataset search) | 2h | HuggingFace MCP |
| 3 | Agent Doctor (teacher data gen) | 3h | mascarade Router |
| 4 | Agent Archiviste (HF push) | 2h | HuggingFace token |
| 5 | Agent Student (LoRA fine-tune) | 4h | llama.cpp + trl |
| 6 | P2P task handlers | 2h | mesh P2P actif |
| 7 | Agent Analyste | 3h | Student output |
| 8 | Agent Renforceur (DPO) | 4h | Analyste + Doctor |
| 9 | Agent Validateur | 3h | Student output |
| 10 | Orchestrateur pipeline | 3h | Tous les agents |
| 11 | Auto-registration provider | 2h | llama-server |
| 12 | Cycle continu | 2h | Orchestrateur |
