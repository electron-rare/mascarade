# 🚀 Guide de Démarrage Rapide

Ce guide vous permettra de démarrer avec le système Kanban IA P2P en moins de 10 minutes.

## ⚡ Installation Express (5 minutes)

### 1. Cloner le Projet

```bash
git clone <votre-repo>
cd KanbanAI
```

### 2. Configuration SSH

Configurez l'authentification par clé SSH pour tous les nœuds :

```bash
make setup-ssh
```

Cette commande va :
- ✅ Générer une clé SSH si nécessaire
- ✅ Copier la clé vers tous vos nœuds P2P
- ✅ Configurer l'authentification automatique

### 3. Déploiement

Déployez le système IA sur tous les nœuds :

```bash
make deploy-all
```

Cela va :
- ✅ Copier le script Python sur chaque nœud
- ✅ Créer les répertoires nécessaires
- ✅ Tester les connexions
- ✅ Afficher un rapport de statut

### 4. Vérification

Vérifiez que tout fonctionne :

```bash
make test-remote-all
```

Vous devriez voir le statut de chaque nœud s'afficher.

### 5. Lancement

Compilez et lancez l'application :

```bash
make run
```

**C'est tout ! 🎉**

---

## 📝 Configuration Personnalisée

### Modifier les Nœuds

Éditez `Config/nodes.json` pour personnaliser vos nœuds :

```json
{
  "name": "Mon Serveur",
  "host": "192.168.1.100",
  "port": 22,
  "username": "user",
  "capabilities": ["textProcessing", "inference"]
}
```

### Ajouter des Capacités IA

Installez les bibliothèques Python sur vos nœuds :

```bash
# Sur le nœud distant
ssh user@host
pip3 install transformers torch numpy pillow
```

Ou automatiquement :

```bash
make install-deps
```

---

## 🎯 Utilisation Basique

### Créer une Tâche

1. Cliquez sur le bouton **"+"** ou appuyez sur **⌘N**
2. Remplissez le titre et la description
3. Choisissez la priorité et le statut
4. Cliquez sur **"Créer"**

### Traiter avec l'IA

1. Cliquez sur le menu **⋯** d'une tâche
2. Sélectionnez **"Traiter avec IA"**
3. Choisissez la capacité (ex: "Traitement de texte")
4. La tâche sera automatiquement envoyée au meilleur nœud disponible

### Déplacer une Tâche

1. Cliquez sur le menu **⋯** d'une tâche
2. Sélectionnez **"Déplacer vers"**
3. Choisissez le nouveau statut

---

## 🔧 Commandes Utiles

### Développement

```bash
# Build et test
make dev

# Nettoyer
make clean

# Tests uniquement
make test
```

### Déploiement

```bash
# Vérifier les nœuds
make deploy-check

# Déployer sur un nœud spécifique
make deploy-root
make deploy-clems
make deploy-kxkm
make deploy-cils

# Déploiement complet (avec dépendances)
make full-deploy
```

### Monitoring

```bash
# Statut de tous les nœuds
make status

# Logs d'un nœud
make logs-root
make logs-clems

# Logs de tous les nœuds
make logs-all
```

### SSH Direct

```bash
# Connexion directe aux nœuds
make ssh-root
make ssh-clems
make ssh-kxkm
make ssh-cils
```

---

## 🐛 Dépannage Express

### Les nœuds n'apparaissent pas en ligne

```bash
# Vérifier la connectivité
ping 192.168.0.119

# Tester SSH
ssh root@192.168.0.119 echo "test"

# Redéployer
make deploy-all
```

### Erreur d'authentification SSH

```bash
# Reconfigurer SSH
make setup-ssh

# Vérifier les permissions
chmod 600 ~/.ssh/id_ed25519
```

### Le script Python ne fonctionne pas

```bash
# Vérifier Python sur le nœud
ssh root@192.168.0.119 "python3 --version"

# Tester le script
make test-remote-root

# Voir les logs
make logs-root
```

---

## 📚 Ressources

- **README.md** - Documentation complète
- **ANALYSIS.md** - Analyse technique détaillée
- **Config/nodes.json** - Configuration des nœuds
- **Makefile** - Toutes les commandes disponibles (`make help`)

---

## 💡 Astuces

### Raccourcis Clavier

- **⌘N** - Nouvelle tâche
- **⌘R** - Rafraîchir les nœuds
- **⌘⇧P** - Traiter avec IA
- **⌘D** - Marquer comme terminé
- **⌘⇧M** - Gérer les nœuds

### Performance

- Configurez `maxConcurrentTasks` dans les paramètres
- Ajustez le `refreshInterval` pour moins de requêtes réseau
- Désactivez les nœuds inutilisés dans `Config/nodes.json`

### Sécurité

- Utilisez **uniquement** des clés SSH (pas de mots de passe)
- Limitez les permissions sur les nœuds distants
- Vérifiez régulièrement les logs (`make logs-all`)

---

## 🎓 Prochaines Étapes

1. ✅ **Explorez l'interface** - Familiarisez-vous avec le tableau Kanban
2. ✅ **Créez des tâches** - Testez les différentes priorités et tags
3. ✅ **Testez l'IA** - Essayez toutes les capacités IA disponibles
4. ✅ **Monitoring** - Surveillez les nœuds et les statistiques
5. ✅ **Personnalisez** - Adaptez à vos besoins spécifiques

---

## ❓ Aide

Pour toute question ou problème :

1. Consultez le **README.md** pour la documentation complète
2. Vérifiez **ANALYSIS.md** pour les détails techniques
3. Utilisez `make help` pour voir toutes les commandes disponibles
4. Consultez les logs avec `make logs-all`

---

**Bon développement ! 🚀**
