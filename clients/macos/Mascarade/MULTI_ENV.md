# 🚀 Guide Multi-Environnements

## Vue d'Ensemble

Le système KanbanAI supporte maintenant **3 environnements** :

- **Development** 🔵 - Développement local
- **Staging** 🟡 - Tests en conditions réelles
- **Production** 🟢 - Déploiement production

---

## 📁 Structure des Configurations

```
Config/
├── environments.json          # Configuration multi-env
└── nodes.json                 # Configuration legacy (dev only)

Sources/Core/Config/
├── Environment.swift          # Enum et configs
└── ConfigurationManager.swift # Gestionnaire de config

Scripts/
├── build.sh                   # Build multi-env
└── deploy.sh                  # Déploiement multi-env
```

---

## 🔧 Configuration par Environnement

### Development 🔵

**Caractéristiques :**
- Logs verbeux activés
- Timeout courts (10s)
- Retry limités (2)
- Nœuds locaux (localhost)
- Debug UI activé

**Nœuds :**
```
localhost:2222 (dev)
127.0.0.1:2223 (test)
```

**Usage :**
```bash
make build-dev
make run-dev
make dev          # build + test
```

### Staging 🟡

**Caractéristiques :**
- Logs informatifs
- Timeout moyens (20s)
- Retry modérés (3)
- Nœuds staging (192.168.1.x)
- Métriques activées

**Nœuds :**
```
staging@192.168.1.119
staging@192.168.1.120
```

**Usage :**
```bash
make build-staging
make deploy-staging
make staging-full  # build + deploy complet
```

### Production 🟢

**Caractéristiques :**
- Logs warnings/errors uniquement
- Timeout longs (30s)
- Retry max (5)
- Nœuds production (vos 4 machines)
- Alertes et backup activés

**Nœuds :**
```
root@192.168.0.119
clems@192.168.0.120
kxkm@kxkm-ai
user@cils
```

**Usage :**
```bash
make build-prod
make deploy-prod        # avec confirmation
make deploy-prod-force  # sans confirmation
make prod-full          # pipeline complet
```

---

## 🛠️ Commandes Make

### Build

```bash
# Build avec environnement par défaut (dev)
make build

# Build spécifique
make build ENVIRONMENT=development
make build ENVIRONMENT=staging
make build ENVIRONMENT=production

# Raccourcis
make build-dev
make build-staging
make build-prod

# Build tous les environnements
make build-all
```

### Run

```bash
# Run avec environnement actuel
make run

# Run spécifique
make run ENVIRONMENT=development
make run-dev
make run-staging
```

### Deploy

```bash
# Déploiement (avec tests et backup)
make deploy ENVIRONMENT=production

# Raccourcis
make deploy-dev
make deploy-staging
make deploy-prod
make deploy-prod-force  # sans confirmation

# Pipelines complets
make dev-run           # build + run dev
make staging-full      # build + deploy staging
make prod-full         # build + test + deploy prod
```

### Rollback

```bash
# Rollback vers version précédente
make rollback ENVIRONMENT=production
make rollback-prod
```

---

## 📋 Scripts de Build

### build.sh

**Usage :**
```bash
./Scripts/build.sh [ENVIRONMENT] [OPTIONS]

# Exemples
./Scripts/build.sh dev
./Scripts/build.sh staging --clean
./Scripts/build.sh prod --test --archive
```

**Options :**
- `--clean` : Nettoyer avant build
- `--test` : Exécuter les tests
- `--archive` : Créer une archive
- `--run` : Lancer après build

**Sortie :**
- Binaire : `.build/[Debug|Release]/KanbanAI`
- Archive : `Archives/KanbanAI_[env]_[timestamp].tar.gz`
- Config : `.env` avec variables d'environnement

### deploy.sh

**Usage :**
```bash
./Scripts/deploy.sh [ENVIRONMENT] [OPTIONS]

# Exemples
./Scripts/deploy.sh dev
./Scripts/deploy.sh staging --skip-tests
./Scripts/deploy.sh prod --force
```

**Options :**
- `--skip-build` : Ne pas rebuilder
- `--skip-tests` : Ne pas tester
- `--skip-backup` : Ne pas backup
- `--force` : Sans confirmation
- `--rollback` : Revenir en arrière

**Process :**
1. ✅ Confirmation (prod seulement)
2. ✅ Backup automatique
3. ✅ Tests
4. ✅ Build
5. ✅ Déploiement scripts IA
6. ✅ Health check
7. ✅ Vérification finale

---

## 🔄 Workflows Typiques

### Développement Quotidien

```bash
# 1. Coder
vim Sources/...

# 2. Tester
make test

# 3. Build & Run
make dev-run

# 4. Vérifier
make status
```

### Release vers Staging

```bash
# 1. Tests complets
make test

# 2. Build staging
make build-staging

# 3. Déployer
make deploy-staging

# 4. Vérifier
make status
make logs-all

# 5. Tester les fonctionnalités
# ...

# 6. Si OK, passer en prod
```

### Release Production

```bash
# 1. Vérifier que staging fonctionne
make status ENVIRONMENT=staging

# 2. Créer backup
make backup ENVIRONMENT=production

# 3. Pipeline complet
make prod-full
# ou étape par étape :
make test
make build-prod
make deploy-prod

# 4. Monitoring
make status
make logs-all

# 5. Si problème : rollback
make rollback-prod
```

---

## 🔐 Variables d'Environnement

### .env (auto-généré)

```bash
ENVIRONMENT=production
CONFIGURATION=Release
BUILD_DATE=2026-03-22T15:30:00Z
```

### Environment.swift

```swift
#if DEBUG
  // Development
  return .development
#elseif STAGING
  // Staging
  return .staging
#else
  // Production
  return .production
#endif
```

---

## 📊 Configuration Manager

### Utilisation dans le Code

```swift
// Obtenir la configuration actuelle
let config = await ConfigurationManager.shared

// Environnement actuel
let env = await config.getCurrentEnvironment()
// .development | .staging | .production

// Charger les nœuds
let nodes = await config.getNodes()

// Paramètres
let timeout = await config.getTimeout()
let retries = await config.getRetryAttempts()

// Feature flags
if await config.isFeatureEnabled(.debugUI) {
    // Afficher debug UI
}

if await config.isFeatureEnabled(.metrics) {
    // Enregistrer métriques
}
```

### Personnalisation

Modifier `Config/environments.json` :

```json
{
  "production": {
    "settings": {
      "connectionTimeout": 60,  // ← Augmenter
      "maxConcurrentTasks": 20, // ← Plus de parallélisme
      "enableMetrics": true,
      "metricsInterval": 600
    }
  }
}
```

---

## 🎯 Feature Flags

| Feature | Dev | Staging | Prod | Description |
|---------|-----|---------|------|-------------|
| `debugUI` | ✅ | ❌ | ❌ | UI de debug |
| `mockMode` | ✅ | ❌ | ❌ | Mode mock (sans SSH) |
| `metrics` | ❌ | ✅ | ✅ | Collecte de métriques |
| `alerts` | ❌ | ✅ | ✅ | Alertes système |
| `backup` | ❌ | ✅ | ✅ | Backup automatique |

---

## 📈 Monitoring par Environnement

### Development

```bash
# Logs locaux
tail -f Logs/app.log

# Status rapide
make demo-quick
```

### Staging

```bash
# Status des nœuds
make status ENVIRONMENT=staging

# Logs
ssh staging@192.168.1.119 "tail -f /var/log/mascarade_ai_*.log"
```

### Production

```bash
# Health check complet
make status

# Tous les logs
make logs-all

# Métriques
# (si configuré)
```

---

## 🔧 Troubleshooting

### "Environment not found"

**Problème :** Configuration manquante

**Solution :**
```bash
# Vérifier le fichier existe
ls -l Config/environments.json

# Valider le JSON
python3 -m json.tool Config/environments.json
```

### "Build failed"

**Problème :** Erreur de compilation

**Solution :**
```bash
# Clean complet
make clean-all

# Rebuild
make build-dev --verbose
```

### "Deploy failed"

**Problème :** Nœuds inaccessibles

**Solution :**
```bash
# Vérifier connectivité
make status

# Tester SSH
ssh root@192.168.0.119 echo "test"

# Redéployer scripts IA
make deploy-ai
```

### "Rollback needed"

**Problème :** Version problématique

**Solution :**
```bash
# Rollback immédiat
make rollback-prod

# Vérifier la restauration
make status
make logs-all
```

---

## 📦 Archives et Backups

### Créer une Archive

```bash
# Archive de l'environnement actuel
make archive ENVIRONMENT=production

# Toutes les archives
make archive-all
```

**Contenu :**
- Binaire compilé
- Configuration
- Scripts IA
- README d'installation

### Backups

```bash
# Backup manuel
make backup ENVIRONMENT=production

# Restaurer
make restore BACKUP_FILE=Backups/backup_production_20260322_153000.tar.gz
```

**Backups automatiques :**
- Avant chaque déploiement (staging/prod)
- Interval configurable en prod (default: 1h)

---

## 🚦 CI/CD Pipeline

### Simulation Locale

```bash
# Pipeline CI
make ci        # clean + test + build

# Pipeline CD (dev)
make cd-dev    # ci + deploy-dev

# Pipeline CD (staging)
make cd-staging

# Pipeline CD (prod)
make cd-prod   # ci seulement, deploy manuel
```

### Intégration GitHub Actions (exemple)

```yaml
name: CI/CD

on:
  push:
    branches: [main, develop]

jobs:
  test:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: make test

  build-staging:
    if: github.ref == 'refs/heads/develop'
    needs: test
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build staging
        run: make build-staging

  build-production:
    if: github.ref == 'refs/heads/main'
    needs: test
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build production
        run: make build-prod
```

---

## 📚 Résumé des Commandes

| Tâche | Dev | Staging | Prod |
|-------|-----|---------|------|
| **Build** | `make build-dev` | `make build-staging` | `make build-prod` |
| **Run** | `make run-dev` | `make run-staging` | - |
| **Deploy** | `make deploy-dev` | `make deploy-staging` | `make deploy-prod` |
| **Test** | `make test` | `make test` | `make test` |
| **Status** | `make demo-quick` | `make status` | `make status` |
| **Logs** | `tail -f Logs/app.log` | `make logs-all` | `make logs-all` |
| **Rollback** | - | `make rollback` | `make rollback-prod` |

---

**Système multi-environnements opérationnel ! 🎉**

Passez facilement entre dev, staging et production avec une simple variable d'environnement.
