# 🚀 BUILD & RUN - KanbanAI

## ⚡ Build Rapide

### Option 1: Script Automatique (Recommandé)

```bash
chmod +x quick-build.sh
./quick-build.sh
```

### Option 2: Script Complet (Build + Tests)

```bash
chmod +x test-build.sh
./test-build.sh
```

### Option 3: Commandes Swift Directes

```bash
# Build
swift build

# Run
swift run KanbanAI

# Tests
swift test
```

---

## 📁 Structure du Projet

```
KanbanAI/
├── Package.swift                    # Configuration SPM
├── Sources/
│   └── KanbanAI/
│       ├── main.swift              # Point d'entrée
│       └── Models/
│           ├── KanbanTask.swift    # Modèle de tâche
│           └── P2PNode.swift       # Modèle de nœud
└── Tests/
    └── KanbanAITests/
        └── KanbanAITests.swift     # Tests unitaires
```

---

## ✅ Vérifier le Build

Après le build, vous devriez voir :

```
🚀 KanbanAI - Système Kanban avec IA Distribuée P2P
============================================================

📋 Tâches Kanban:

  📝 [À faire] 🟠 Implémenter l'authentification
     └─ Ajouter OAuth2 et JWT
     └─ Tags: backend, sécurité

  ⚙️ [En cours] 🟡 Analyser les performances
     └─ Optimiser les requêtes SQL
     └─ Tags: performance, database

  ✅ [Terminé] 🟢 Tests d'intégration
     └─ Couvrir les endpoints API
     └─ Tags: tests, qualité

============================================================

🌐 Nœuds P2P configurés:

  🔴 Root Server
     └─ root@192.168.0.119
     └─ Capacités: Traitement de données, Entraînement de modèles, Inférence

  🔴 Clems Workstation
     └─ clems@192.168.0.120
     └─ Capacités: Traitement de texte, Analyse d'images, Inférence

  🔴 KXKM AI Node
     └─ kxkm@kxkm-ai
     └─ Capacités: Entraînement de modèles, Inférence, Traitement de données

  🔴 CILS Node
     └─ user@cils
     └─ Capacités: Traitement de texte, Inférence

============================================================

📊 Statistiques:
  Tâches totales  : 3
  Tâches terminées: 1
  Taux complétion : 33.3%
  Nœuds P2P       : 4

✅ Application KanbanAI initialisée avec succès!

💡 Prochaines étapes:
  1. Configurer SSH pour les nœuds P2P
  2. Déployer les scripts IA: make deploy-ai
  3. Lancer l'interface graphique (à venir)
```

---

## 🧪 Tests

Les tests vérifient :

✅ Création de tâches  
✅ Statuts et priorités  
✅ Encodage/Décodage JSON  
✅ Création de nœuds  
✅ Connexions SSH  
✅ Capacités IA  
✅ Nœuds prédéfinis  

```bash
# Lancer les tests
swift test

# Tests avec output détaillé
swift test --verbose
```

---

## 🔧 Troubleshooting

### "No such module 'KanbanAI'"

```bash
swift package clean
swift package resolve
swift build
```

### "Build failed"

```bash
# Vérifier Swift version
swift --version  # Besoin 5.9+

# Clean complet
rm -rf .build
swift package clean
swift build
```

### Tests échouent

```bash
# Rebuild tout
swift package clean
swift build
swift test
```

---

## 📊 Informations Build

### Binaire Généré

```bash
.build/debug/KanbanAI        # Version Debug
.build/release/KanbanAI      # Version Release (après swift build -c release)
```

### Taille

```bash
# Debug (~2-3 MB)
du -h .build/debug/KanbanAI

# Release (~1-2 MB)
du -h .build/release/KanbanAI
```

---

## 🚀 Build Release

Pour production :

```bash
# Build optimisé
swift build -c release

# Run
.build/release/KanbanAI
```

---

## ✅ Statut

**Version actuelle : CLI Console**

- ✅ Modèles de données (Task, Node)
- ✅ Affichage console
- ✅ Tests unitaires
- ✅ Structure complète
- 🔄 Interface graphique SwiftUI (prochaine étape)
- 🔄 Services P2P SSH (prochaine étape)
- 🔄 IA distribuée (prochaine étape)

---

## 📝 Prochaines Étapes

1. **Interface SwiftUI** - Ajouter vues graphiques
2. **Services P2P** - Implémenter connexions SSH
3. **IA Distribuée** - Intégrer traitement sur nœuds
4. **Persistance** - Sauvegarder les données

---

**Build et teste en une commande:**

```bash
chmod +x test-build.sh && ./test-build.sh
```

🎉 **L'application compile et fonctionne !**
