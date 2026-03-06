# Stratégie de Fine-Tuning pour EDA (Spice & KiCad)

## 📋 Synthèse des Recherches

### 1. SPICE Simulation
**Dataset Recommandé :** SPICEPilot
- **Source :** [GitHub - ACADLab/SPICEPilot](https://github.com/acadlab/spicepilot)
- **Format :** Netlists SPICE, analyses AC/DC/transitoire, débogage
- **Taille :** ~500 exemples de qualité professionnelle
- **Avantages :** Généré avec PySpice, benchmarks standardisés

**Modèle Recommandé :** Mistral-7B finetuné avec SPICEPilot
- **Pourquoi :** Excellente génération de code technique
- **Approche :** Fine-tuning sur SPICEPilot + données spécifiques

### 2. KiCad PCB Design
**Dataset Recommandé :** Projets communautaires KiCad
- **Sources :**
  - [Forum KiCad Dataset Request](https://forum.kicad.info/t/seeking-a-samples-of-kicad-projects-schematics-pcbs-for-a-non-commercial-research-dataset/61531)
  - Projets GitHub (recherche "KiCad PCB")
- **Format :** Fichiers `.kicad_sch` + `.kicad_pcb` + netlists
- **Outils :** [KiCad MCP Server](https://github.com/mixelpixx/kicad-mcp-server)

**Modèle Recommandé :** CircuitLM ou Mistral-7B finetuné
- **CircuitLM :** Spécialisé pour schématiques PCB
- **PCBSchemaGen :** Constraint-guided PCB layout

### 3. Modèles Spécialisés EDA

| Modèle          | Domaine                  | Avantages                          | Source |
|-----------------|--------------------------|-----------------------------------|--------|
| **CircuitLM**   | Schématiques PCB         | Constraint-guided, haute précision | [arXiv](https://arxiv.org/html/2602.00510) |
| **SpecLLM**     | VLSI/HDL                 | Natural language → hardware        | [GitHub](https://github.com/Thinklab-SJTU/Awesome-LLM4EDA) |
| **PCBSchemaGen**| Layout PCB               | Intégration avec outils EDA       | [arXiv](https://arxiv.org/html/2602.00510) |
| **SPICEPilot**  | Simulation SPICE         | Génération de netlists            | [GitHub](https://github.com/acadlab/spicepilot) |

## 🎯 Plan d'Exécution Détaillé

### Phase 1 : Préparation des Datasets (Semaine 1)

#### 📌 Tâche 1.1 : Dataset SPICE
```bash
# 1. Télécharger SPICEPilot
cd finetune/datasets
git clone https://github.com/acadlab/spicepilot.git spicepilot

# 2. Préparer pour Mistral Studio
cd spicepilot
python prepare_dataset.py --format mistral --output ../spice_mistral.jsonl

# 3. Valider le dataset
python validate_spice_dataset.py
```

**Fichiers attendus :**
- `finetune/datasets/spice_mistral.jsonl` (format Mistral Studio)
- `finetune/datasets/spice_validation_report.txt`

#### 📌 Tâche 1.2 : Dataset KiCad
```bash
# 1. Créer structure de dataset
mkdir -p finetune/datasets/kicad/projects

# 2. Télécharger projets exemples
# Option A: Depuis GitHub (exemple)
git clone https://github.com/kicad/kicad-demos.git kicad/projects/demo1

# Option B: Depuis forum KiCad
# Télécharger manuellement et placer dans kicad/projects/

# 3. Convertir en format Mistral
python finetune/build_kicad_dataset.py --input kicad/projects --output kicad_mistral.jsonl
```

**Fichiers attendus :**
- `finetune/datasets/kicad_mistral.jsonl`
- `finetune/datasets/kicad_projects_list.txt`

### Phase 2 : Création des Agents Spécialisés (Semaine 1-2)

#### 📌 Tâche 2.1 : Agent SPICE
```python
# Fichier: core/mascarade/agents/spice_agent.py

class SpiceAgent(Agent):
    def __init__(self):
        super().__init__(
            name="spice-expert",
            description="Expert en simulation SPICE - netlists, analyses, débogage",
            system_prompt=(
                "You are an expert SPICE simulation engineer. "
                "Generate accurate netlists, perform AC/DC/transient analysis, "
                "debug convergence issues, and explain circuit behavior. "
                "Always provide complete, simulatable SPICE code."
            ),
            preferred_provider="mistral",
            preferred_model="mistral-large-latest",
            tools=["python", "spice_simulator"],
            temperature=0.1,
            max_tokens=3072,
        )

    async def generate_netlist(self, circuit_description: str, router) -> str:
        # Génère un netlist SPICE complet
        pass

    async def debug_convergence(self, error_message: str, netlist: str, router) -> str:
        # Débogue les problèmes de convergence
        pass
```

#### 📌 Tâche 2.2 : Agent KiCad
```python
# Fichier: core/mascarade/agents/kicad_agent.py

class KiCadAgent(Agent):
    def __init__(self):
        super().__init__(
            name="kicad-designer",
            description="Expert KiCad - schématiques, layout PCB, règles de design",
            system_prompt=(
                "You are an expert KiCad PCB designer. "
                "Create schematics, optimize layouts, apply design rules, "
                "generate manufacturing files, and provide best practices. "
                "Always follow KiCad conventions and include DRC checks."
            ),
            preferred_provider="mistral",
            preferred_model="mistral-large-latest",
            tools=["kicad_api", "python"],
            temperature=0.2,
            max_tokens=2048,
        )

    async def generate_schematic(self, requirements: str, router) -> str:
        # Génère un schéma KiCad
        pass

    async def optimize_layout(self, constraints: str, router) -> str:
        # Optimise le layout PCB
        pass
```

**Fichiers attendus :**
- `core/mascarade/agents/spice_agent.py`
- `core/mascarade/agents/kicad_agent.py`
- Mise à jour de `core/mascarade/agents/__init__.py`
- Mise à jour de `core/mascarade/agents/skills.py`

### Phase 3 : Fine-Tuning avec Mistral Studio (Semaine 2-3)

#### 📌 Tâche 3.1 : Notebook SPICE
```python
# Fichier: finetune/notebooks/finetune_spice_mistral.ipynb

# Contenu:
1. Chargement du dataset SPICEPilot
2. Préparation pour Mistral Studio
3. Soumission du job de fine-tuning
4. Monitoring de la progression
5. Test du modèle finetuné
6. Intégration avec Mascarade
```

#### 📌 Tâche 3.2 : Notebook KiCad
```python
# Fichier: finetune/notebooks/finetune_kicad_mistral.ipynb

# Contenu:
1. Chargement du dataset KiCad
2. Préparation pour Mistral Studio
3. Soumission du job de fine-tuning
4. Monitoring de la progression
5. Test du modèle finetuné
6. Intégration avec Mascarade
```

**Commandes Mistral Studio :**
```bash
# Soumettre un job de fine-tuning
mistral fine-tuning create \
  --model mistral-large-latest \
  --training-data finetune/datasets/spice_mistral.jsonl \
  --name spice-expert-v1 \
  --hyperparameters '{"epochs": 3, "learning_rate": 2e-5}'
```

### Phase 4 : Intégration dans Mascarade (Semaine 3)

#### 📌 Tâche 4.1 : Configuration des Providers
```python
# Mettre à jour core/mascarade/router/providers/mistral.py
# Ajouter les modèles finetunés

def available_models(self) -> list[str]:
    return [
        "mistral-large-latest",
        "mistral-small-latest",
        "codestral-latest",
        "ft:spice-expert-v1",      # Modèle SPICE finetuné
        "ft:kicad-designer-v1"     # Modèle KiCad finetuné
    ]
```

#### 📌 Tâche 4.2 : Tests d'Intégration
```bash
# Test complet
cd core
python -c "
from mascarade.agents import SpiceAgent, KiCadAgent
from mascarade.router import Router

# Test Spice Agent
spice_agent = SpiceAgent()
print(f'✓ Spice Agent: {spice_agent.name}')

# Test KiCad Agent
kicad_agent = KiCadAgent()
print(f'✓ KiCad Agent: {kicad_agent.name}')

# Test Router
router = Router()
print(f'✓ Modèles disponibles: {router.available_models()}')
"
```

### Phase 5 : Schématique & Routage (Semaine 4)

#### 📌 Tâche 5.1 : Dataset Schématique
```bash
# Utiliser PCBSchemaGen dataset
git clone https://github.com/PCBSchemaGen/dataset.git
python convert_schematic_dataset.py
```

#### 📌 Tâche 5.2 : Dataset Routage
```bash
# Collecter des exemples de routage
python build_routing_dataset.py --source kicad_projects
```

## 📅 Calendrier Prévisionnel

| Phase | Durée | Livrables | Responsable |
|-------|-------|-----------|-------------|
| 1. Datasets | 1 sem | Datasets SPICE & KiCad prêts | Vous |
| 2. Agents | 1 sem | Agents Spice & KiCad intégrés | Vous |
| 3. Fine-Tuning | 1-2 sem | Modèles finetunés opérationnels | Mistral Studio |
| 4. Intégration | 1 sem | Tout intégré dans Mascarade | Vous |
| 5. Avancé | 1 sem | Schématique & routage | Vous |

## 🎯 Résultats Attendus

1. **Modèle SPICE finetuné** capable de:
   - Générer des netlists corrects
   - Déboguer les problèmes de convergence
   - Expliquer les résultats de simulation

2. **Modèle KiCad finetuné** capable de:
   - Créer des schématiques optimisés
   - Appliquer les règles de design
   - Générer des fichiers de fabrication

3. **Intégration complète** dans Mascarade avec:
   - Agents spécialisés accessibles via API
   - Routage intelligent vers les modèles finetunés
   - Interface unifiée pour toutes les tâches EDA

## 🚀 Prochaines Actions Immédiates

1. **Télécharger SPICEPilot** :
   ```bash
   cd finetune/datasets
   git clone https://github.com/acadlab/spicepilot.git
   ```

2. **Créer l'agent SPICE** :
   ```bash
   touch core/mascarade/agents/spice_agent.py
   ```

3. **Préparer le notebook SPICE** :
   ```bash
   cp finetune/notebooks/finetune_freecad_mistral_studio.ipynb \
      finetune/notebooks/finetune_spice_mistral.ipynb
   ```

4. **Configurer votre clé API Mistral** (déjà fait) :
   ```bash
   # Vérifiez dans .env
   grep MISTRAL_API_KEY .env
   ```

## 📚 Ressources Clés

- **SPICEPilot** : https://github.com/acadlab/spicepilot
- **CircuitLM** : https://arxiv.org/html/2602.00510
- **KiCad MCP Server** : https://github.com/mixelpixx/kicad-mcp-server
- **Mistral Studio** : https://console.mistral.ai/
- **Documentation Mascarade** : docs/MISTRAL_STUDIO_INTEGRATION.md

---

*Document généré le 2024-06-06 pour le projet Mascarade EDA Integration*
*Stratégie basée sur les meilleures pratiques EDA et LLM (2024-2026)*
