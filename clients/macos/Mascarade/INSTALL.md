# 🚀 KanbanAI - Installation & Lancement

## ⚡ Installation Express (2 minutes)

### Prérequis
- macOS 13.0+ (Ventura ou supérieur)
- Xcode Command Line Tools
- Swift 5.9+

### Installation Automatique

```bash
# 1. Rendre le script exécutable
chmod +x Scripts/setup-app.sh

# 2. Lancer le setup
./Scripts/setup-app.sh
```

Le script va :
- ✅ Vérifier les prérequis
- ✅ Créer la structure de répertoires
- ✅ Configurer les scripts
- ✅ Résoudre les dépendances
- ✅ Builder l'application
- ✅ Créer la configuration initiale

### Installation Manuelle

```bash
# 1. Résoudre les dépendances
swift package resolve

# 2. Builder l'application
swift build

# 3. Lancer
.build/debug/KanbanAI
```

---

## 🎯 Démarrage Rapide

### Option 1: Makefile (Recommandé)

```bash
# Development
make dev-run

# Staging
make staging-full

# Production
make prod-full
```

### Option 2: Swift Direct

```bash
# Build
swift build

# Run
swift run KanbanAI

# Tests
swift test
```

### Option 3: Exécutable Direct

```bash
# Après build
.build/debug/KanbanAI
```

---

## 📁 Structure du Projet

```
KanbanAI/
├── Sources/
│   ├── main.swift                    # Point d'entrée
│   ├── Core/
│   │   ├── Models/
│   │   │   ├── KanbanTask.swift
│   │   │   └── P2PNode.swift
│   │   ├── Services/
│   │   │   ├── P2PConnectionManager.swift
│   │   │   └── AITaskExecutor.swift
│   │   ├── Config/
│   │   │   ├── Environment.swift
│   │   │   └── ConfigurationManager.swift
│   │   └── ViewModels/
│   │       └── KanbanBoard.swift
│   └── UI/
│       └── Views/
│           ├── KanbanBoardView.swift
│           ├── KanbanColumn.swift
│           ├── AddTaskView.swift
│           └── NodeManagerView.swift
│
├── Tests/
│   └── KanbanAITests.swift
│
├── Scripts/
│   ├── setup-app.sh              # Setup initial
│   ├── build.sh                  # Build multi-env
│   ├── deploy.sh                 # Déploiement
│   ├── env-switch.sh             # Switch env
│   ├── mascarade_ai.py           # IA P2P
│   └── deploy_mascarade.sh       # Deploy IA
│
├── Config/
│   ├── environments.json         # Config multi-env
│   └── nodes.json               # Config nœuds (legacy)
│
├── Package.swift                # Configuration SPM
└── Makefile                     # Automatisation
```

---

## 🔧 Configuration

### Environnements Disponibles

**Development** 🔵
- Nœuds: localhost
- Logs: DEBUG
- Usage: `make dev-run`

**Staging** 🟡
- Nœuds: 192.168.1.x
- Logs: INFO
- Usage: `make staging-full`

**Production** 🟢
- Nœuds: vos 4 machines
- Logs: WARNING
- Usage: `make prod-full`

### Switch d'Environnement

```bash
# Interactif
./Scripts/env-switch.sh

# Direct
make build ENVIRONMENT=development
make build ENVIRONMENT=staging
make build ENVIRONMENT=production
```

---

## 🎮 Utilisation

### Interface Principale

1. **Créer une tâche**
   - Cliquez sur "+" ou ⌘N
   - Remplissez titre, description, priorité
   - Ajoutez des tags (optionnel)

2. **Traiter avec l'IA**
   - Menu ⋯ sur une tâche
   - "Traiter avec IA"
   - Choisir la capacité (texte, image, data, etc.)

3. **Déplacer une tâche**
   - Menu ⋯ → "Déplacer vers"
   - Sélectionner le nouveau statut

4. **Gérer les nœuds**
   - Sidebar → "Gérer les nœuds"
   - Ajouter/Modifier/Supprimer

### Raccourcis Clavier

- **⌘N** - Nouvelle tâche
- **⌘R** - Rafraîchir nœuds
- **⌘⇧P** - Traiter avec IA
- **⌘D** - Marquer comme terminé
- **⌘⇧M** - Gérer nœuds

---

## 🤖 Configuration IA P2P

### 1. Déployer les Scripts

```bash
# Tous les nœuds
make deploy-ai

# Vérifier
make deploy-ai-check
```

### 2. Configurer SSH

```bash
# Générer clé si besoin
ssh-keygen -t ed25519 -C "kanban-ai"

# Copier vers les nœuds
ssh-copy-id root@192.168.0.119
ssh-copy-id clems@192.168.0.120
ssh-copy-id kxkm@kxkm-ai
ssh-copy-id user@cils
```

### 3. Tester

```bash
# Status des nœuds
make status

# Test rapide
make demo-quick
```

---

## 📊 Commandes Utiles

### Build & Run
```bash
make build           # Build (env actuel)
make run             # Run
make dev-run         # Build + Test + Run
make test            # Tests
make clean           # Nettoyer
```

### Déploiement
```bash
make deploy-dev
make deploy-staging
make deploy-prod
make rollback-prod   # Rollback
```

### Monitoring
```bash
make status          # Status nœuds
make logs-all        # Tous les logs
make demo            # Démos interactives
```

### Helpers
```bash
make help            # Aide complète
make stats           # Statistiques
make env-info        # Info environnement
```

---

## 🐛 Troubleshooting

### Build échoue

```bash
# Nettoyer et rebuilder
make clean
swift package resolve
swift build
```

### Nœuds inaccessibles

```bash
# Vérifier SSH
ssh root@192.168.0.119 echo "test"

# Vérifier statut
make status

# Redéployer IA
make deploy-ai
```

### Application ne se lance pas

```bash
# Vérifier l'exécutable
ls -lh .build/debug/KanbanAI

# Permissions
chmod +x .build/debug/KanbanAI

# Lancer directement
.build/debug/KanbanAI
```

---

## 📚 Documentation

- **README.md** - Documentation complète
- **QUICKSTART.md** - Guide démarrage rapide
- **MULTI_ENV.md** - Multi-environnements
- **EXAMPLES.md** - Exemples pratiques
- **ARCHITECTURE.md** - Architecture technique

---

## 🎓 Premiers Pas

### Workflow Complet

```bash
# 1. Setup
./Scripts/setup-app.sh

# 2. Lancer l'app
make dev-run

# 3. Créer une tâche dans l'interface

# 4. Configurer les nœuds P2P

# 5. Déployer les scripts IA
make deploy-ai

# 6. Traiter une tâche avec l'IA

# 7. Vérifier les résultats
```

---

## ✅ Checklist Post-Installation

- [ ] Application compile
- [ ] Interface se lance
- [ ] Peut créer une tâche
- [ ] Peut voir les nœuds
- [ ] SSH configuré
- [ ] Scripts IA déployés
- [ ] Test d'une tâche IA réussi
- [ ] Documentation lue

---

## 🆘 Support

### Erreurs Communes

**"Command not found: make"**
→ Installer Xcode Command Line Tools: `xcode-select --install`

**"Swift version mismatch"**
→ Vérifier: `swift --version` (besoin 5.9+)

**"SSH connection failed"**
→ Vérifier clés SSH et connectivité réseau

### Ressources

- Documentation complète: `cat README.md`
- Guide rapide: `cat QUICKSTART.md`
- Exemples: `cat EXAMPLES.md`
- Commandes: `make help`

---

## 🎉 C'est Parti !

```bash
# Tout en une commande
./Scripts/setup-app.sh && make dev-run
```

**L'application est prête ! 🚀**

---

**Version:** 1.0.0  
**Plateforme:** macOS 13.0+  
**Swift:** 5.9+  
**Date:** Mars 2026
