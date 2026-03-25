# ⚡ DÉMARRAGE ULTRA-RAPIDE

## 🚀 3 Commandes = Application qui tourne

```bash
# 1. Permissions
chmod +x make-executable.sh && ./make-executable.sh

# 2. Setup
./Scripts/setup-app.sh

# 3. Run
make dev-run
```

**C'est tout ! 🎉**

---

## 📱 L'application devrait s'ouvrir

Si tout fonctionne, vous voyez :
- ✅ Fenêtre KanbanAI
- ✅ Sidebar avec statistiques
- ✅ Tableau Kanban (6 colonnes)
- ✅ Bouton "+" pour créer tâche

---

## 🎯 Premières Actions

### 1. Créer une tâche
- Cliquer sur "+" ou ⌘N
- Titre: "Ma première tâche"
- Priorité: Moyenne
- Créer

### 2. Déplacer la tâche
- Menu ⋯ sur la tâche
- "Déplacer vers" → "En cours"

### 3. Voir les nœuds
- Sidebar → Section "Nœuds P2P"
- Par défaut: 4 nœuds offline (normal sans config SSH)

---

## 🔧 Configuration IA (Optionnel)

### Si vous voulez utiliser l'IA distribuée:

```bash
# 1. Configurer SSH
ssh-keygen -t ed25519
ssh-copy-id root@192.168.0.119
ssh-copy-id clems@192.168.0.120
ssh-copy-id kxkm@kxkm-ai
ssh-copy-id user@cils

# 2. Déployer scripts IA
make deploy-ai

# 3. Vérifier
make status

# 4. Tester
make demo
```

### Dans l'app:
- Créer une tâche
- Menu ⋯ → "Traiter avec IA"
- Choisir capacité (ex: "Traitement de texte")
- La tâche passe en "Traitement IA"

---

## 🐛 Problèmes ?

### App ne compile pas
```bash
swift --version  # Vérifier Swift 5.9+
make clean
swift build
```

### App ne se lance pas
```bash
.build/debug/KanbanAI  # Lancer directement
```

### Besoin d'aide
```bash
make help           # Toutes les commandes
cat INSTALL.md      # Guide complet
cat QUICKSTART.md   # Guide rapide
```

---

## 📚 Documentation

- **INSTALL.md** - Installation complète
- **QUICKSTART.md** - Guide démarrage
- **README.md** - Documentation principale
- **EXAMPLES.md** - Exemples d'utilisation

---

## ✅ Checklist Rapide

- [ ] Scripts exécutables: `./make-executable.sh`
- [ ] Setup: `./Scripts/setup-app.sh`
- [ ] Run: `make dev-run`
- [ ] Interface s'ouvre
- [ ] Tâche créée
- [ ] Tâche déplacée
- [ ] ✨ Ça marche !

---

## 🎯 Commandes Essentielles

```bash
make dev-run        # Build + Run
make test           # Tests
make status         # Status nœuds
make help           # Aide
```

---

**En 3 commandes, l'app tourne ! 🚀**

**Temps total: ~2 minutes**
