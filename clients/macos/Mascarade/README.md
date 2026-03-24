# Système Kanban avec IA Mascarade P2P

Application macOS pour la gestion de tâches Kanban avec traitement IA distribué sur des nœuds P2P via SSH.

## 🎯 Fonctionnalités

### 📋 Gestion Kanban
- Tableau Kanban complet avec 6 colonnes (Backlog, À faire, En cours, Traitement IA, Révision, Terminé)
- Création, modification et suppression de tâches
- Système de priorités (Basse, Moyenne, Haute, Urgente)
- Tags personnalisables
- Statistiques en temps réel

### 🤖 IA Distribuée (Mascarade)
- Traitement IA distribué sur plusieurs nœuds P2P
- 5 capacités IA disponibles:
  - **Traitement de texte** - Analyse NLP, extraction de mots-clés
  - **Analyse d'images** - Détection d'objets, classification
  - **Traitement de données** - Analyse de datasets, transformations
  - **Entraînement de modèles** - ML/DL training distribué
  - **Inférence** - Prédictions avec modèles pré-entraînés

### 🌐 Architecture P2P
- Connexions SSH sécurisées vers les nœuds distants
- Load balancing automatique
- Monitoring de l'état des nœuds en temps réel
- Exécution parallèle de tâches (multitâche)

## 🏗️ Architecture

```
┌─────────────────┐
│   macOS App     │ (Interface SwiftUI)
│   (Frontend)    │
└────────┬────────┘
         │
         │ SSH Connections
         │
    ┌────┴─────────────────────────────────┐
    │                                       │
┌───▼────────┐  ┌────────────┐  ┌─────────▼──┐  ┌──────────┐
│   Node 1   │  │   Node 2   │  │   Node 3   │  │  Node 4  │
│ root@      │  │ clems@     │  │ kxkm@      │  │  cils    │
│ 192.168.   │  │ 192.168.   │  │ kxkm-ai    │  │          │
│ 0.119      │  │ 0.120      │  │            │  │          │
└────────────┘  └────────────┘  └────────────┘  └──────────┘
     ↓               ↓               ↓               ↓
  Python AI      Python AI       Python AI      Python AI
  Mascarade      Mascarade       Mascarade      Mascarade
```

## 🚀 Installation

### Prérequis
- macOS 13.0+ (Ventura ou supérieur)
- Xcode 15.0+
- Swift 5.9+
- Python 3.8+ sur les nœuds distants
- Accès SSH aux nœuds P2P

### Configuration des nœuds P2P

#### 1. Déployer le système IA Mascarade

```bash
# Rendre le script exécutable
chmod +x Scripts/deploy_mascarade.sh

# Déployer sur tous les nœuds
./Scripts/deploy_mascarade.sh --all

# Ou déployer sur des nœuds spécifiques
./Scripts/deploy_mascarade.sh root clems

# Avec service systemd (optionnel)
./Scripts/deploy_mascarade.sh --systemd --all

# Vérifier l'état des nœuds
./Scripts/deploy_mascarade.sh --check
```

#### 2. Configuration SSH

Assurez-vous que l'authentification par clé publique est configurée :

```bash
# Générer une clé SSH si nécessaire
ssh-keygen -t ed25519 -C "mascarade-ai"

# Copier la clé sur chaque nœud
ssh-copy-id root@192.168.0.119
ssh-copy-id clems@192.168.0.120
ssh-copy-id kxkm@kxkm-ai
ssh-copy-id user@cils
```

#### 3. Installer les dépendances Python (optionnel)

Pour activer toutes les capacités IA :

```bash
# Sur chaque nœud
ssh root@192.168.0.119 << 'EOF'
pip3 install numpy pillow transformers torch
EOF
```

### Compilation de l'application macOS

```bash
# Ouvrir le projet dans Xcode
open KanbanAI.xcodeproj

# Ou compiler en ligne de commande
xcodebuild -scheme KanbanAI -configuration Release build
```

## 📱 Utilisation

### Démarrage de l'application

1. Lancer l'application macOS
2. Les nœuds P2P prédéfinis seront automatiquement chargés
3. Cliquer sur "Rafraîchir nœuds" pour vérifier leur disponibilité

### Créer une tâche

1. Cliquer sur le bouton "+" ou "Nouvelle tâche"
2. Remplir les informations :
   - Titre
   - Description
   - Priorité
   - Statut initial
   - Tags (optionnel)
3. Cliquer sur "Créer"

### Traiter une tâche avec l'IA

**Méthode 1 : Tâche individuelle**
1. Cliquer sur le menu ⋯ d'une tâche
2. Sélectionner "Traiter avec IA"
3. Choisir la capacité IA souhaitée
4. La tâche passera automatiquement en "Traitement IA"
5. Une fois terminée, elle passera en "Révision"

**Méthode 2 : Traitement en lot**
1. Dans le menu principal, sélectionner "Actions"
2. Cliquer sur "Traiter toutes les tâches TODO"
3. Toutes les tâches en "À faire" seront traitées en parallèle

### Gérer les nœuds P2P

1. Dans la barre latérale, section "Nœuds P2P"
2. Cliquer sur "Gérer les nœuds"
3. Options disponibles :
   - Ajouter un nouveau nœud
   - Voir les détails d'un nœud
   - Tester la connexion
   - Supprimer un nœud

## 🔧 Configuration

### Nœuds prédéfinis

Les nœuds suivants sont configurés par défaut (modifiable dans `P2PNode.swift`) :

```swift
static let predefinedNodes: [P2PNode] = [
    P2PNode(
        name: "Root Server",
        host: "192.168.0.119",
        username: "root",
        capabilities: [.dataProcessing, .modelTraining, .inference]
    ),
    P2PNode(
        name: "Clems Workstation",
        host: "192.168.0.120",
        username: "clems",
        capabilities: [.textProcessing, .imageAnalysis, .inference]
    ),
    P2PNode(
        name: "KXKM AI Node",
        host: "kxkm-ai",
        username: "kxkm",
        capabilities: [.modelTraining, .inference, .dataProcessing]
    ),
    P2PNode(
        name: "CILS Node",
        host: "cils",
        username: "user",
        capabilities: [.textProcessing, .inference]
    )
]
```

### Personnalisation du script Python

Le script `mascarade_ai.py` peut être personnalisé pour :
- Ajouter de nouvelles capacités IA
- Intégrer vos propres modèles ML
- Modifier la logique de traitement
- Ajouter des logs personnalisés

Exemple d'intégration d'un modèle Hugging Face :

```python
def _handle_text_processing(self, task_data: Dict[str, Any]) -> str:
    from transformers import pipeline
    
    classifier = pipeline("sentiment-analysis")
    text = task_data.get('description', '')
    
    result = classifier(text)
    return json.dumps(result, indent=2)
```

## 📊 Structure du projet

```
.
├── Sources/
│   ├── Core/
│   │   ├── Models/
│   │   │   ├── KanbanTask.swift          # Modèle de tâche Kanban
│   │   │   └── P2PNode.swift             # Modèle de nœud P2P
│   │   ├── Services/
│   │   │   ├── P2PConnectionManager.swift # Gestion des connexions SSH
│   │   │   └── AITaskExecutor.swift       # Exécution des tâches IA
│   │   └── ViewModels/
│   │       └── KanbanBoard.swift          # ViewModel principal
│   └── UI/
│       └── Views/
│           ├── KanbanBoardView.swift      # Vue principale
│           ├── KanbanColumn.swift         # Colonnes du Kanban
│           ├── AddTaskView.swift          # Création de tâches
│           └── NodeManagerView.swift      # Gestion des nœuds
│
├── Scripts/
│   ├── mascarade_ai.py              # Script IA Python
│   └── deploy_mascarade.sh          # Script de déploiement
│
└── README.md
```

## 🎨 Fonctionnalités avancées

### Load Balancing
Le système sélectionne automatiquement le meilleur nœud pour chaque tâche en fonction de :
- La disponibilité du nœud (statut online)
- La charge actuelle (< 80%)
- Les capacités IA disponibles

### Traitement parallèle
Utilisez `processTasksConcurrently` pour traiter plusieurs tâches simultanément :

```swift
await board.processTasksConcurrently(
    tasks,
    capability: .textProcessing
)
```

### Monitoring en temps réel
- Statut des nœuds mis à jour automatiquement
- Progression des tâches en traitement
- Statistiques du tableau (taux de complétion, disponibilité des nœuds)

## 🔒 Sécurité

- **Authentification SSH** : Utilisation de clés publiques/privées
- **Isolation** : Chaque tâche s'exécute dans un processus séparé
- **Logs** : Toutes les opérations sont enregistrées (`/var/log/mascarade/*.log`)
- **Validation** : Les données JSON sont validées avant traitement

## 🐛 Dépannage

### Les nœuds n'apparaissent pas en ligne

```bash
# Vérifier la connectivité SSH
ssh root@192.168.0.119 echo "test"

# Vérifier que le script est déployé
ssh root@192.168.0.119 ls -l /opt/mascarade/mascarade_ai.py

# Tester manuellement
ssh root@192.168.0.119 "python3 /opt/mascarade/mascarade_ai.py status"
```

### Erreurs d'exécution de tâches

Consulter les logs sur le nœud distant :

```bash
ssh root@192.168.0.119 "tail -n 50 /var/log/mascarade_ai_*.log"
```

### Problèmes de permissions

```bash
# Sur le nœud distant
chmod +x /opt/mascarade/mascarade_ai.py
chmod 755 /var/log/mascarade
```

## 📝 TODO / Améliorations futures

- [ ] Chiffrement des communications (SSH tunnel)
- [ ] Authentification multi-facteurs
- [ ] Dashboard de monitoring avancé
- [ ] Support de Docker containers
- [ ] API REST pour intégration externe
- [ ] Base de données persistante (CoreData/SQLite)
- [ ] Export/Import de tâches (JSON, CSV)
- [ ] Notifications push macOS
- [ ] Mode hors ligne avec synchronisation
- [ ] Intégration avec des modèles LLM (GPT, Claude, etc.)

## 🤝 Contribution

Inspiré du projet [Aperant](https://github.com/AndyMik90/Aperant) pour les concepts de :
- Gestion Kanban
- Architecture multitâche
- Intégration IA

## 📄 Licence

Ce projet est sous licence MIT.

## 👨‍💻 Auteur

Développé avec Swift et Python pour macOS.

---

**Note** : Ce projet utilise Swift Concurrency (async/await, actors) pour une gestion moderne de la concurrence et des connexions réseau.
