# ⚡ Quick Reference - Dev & Prod

## 🚀 Démarrage Ultra-Rapide

### Development
```bash
make dev-run
```

### Staging
```bash
make staging-full
```

### Production
```bash
make prod-full
```

---

## 🔄 Switch Environment

### Interactif
```bash
./Scripts/env-switch.sh
```

### Direct
```bash
make build ENVIRONMENT=development
make build ENVIRONMENT=staging
make build ENVIRONMENT=production
```

---

## 📊 3 Environnements

| Env | Nœuds | Timeout | Logs | Usage |
|-----|-------|---------|------|-------|
| 🔵 **Dev** | localhost | 10s | DEBUG | `make dev-run` |
| 🟡 **Staging** | 192.168.1.x | 20s | INFO | `make staging-full` |
| 🟢 **Prod** | 4 machines | 30s | WARNING | `make prod-full` |

---

## 🛠️ Commandes Essentielles

```bash
# Build
make build-dev
make build-staging
make build-prod
make build-all          # tous

# Deploy
make deploy-dev
make deploy-staging
make deploy-prod
make deploy-prod-force  # sans confirmation

# Rollback
make rollback-prod

# Status
make status
make logs-all

# Tests
make test
make ci                 # clean + test + build

# Utils
make help
make demo
```

---

## 📁 Fichiers Clés

```
Config/
└── environments.json   # Configuration 3 env

Sources/Core/Config/
├── Environment.swift
└── ConfigurationManager.swift

Scripts/
├── build.sh           # Build multi-env
├── deploy.sh          # Deploy sécurisé
└── env-switch.sh      # Switch interactif
```

---

## 💡 Use Cases Rapides

### Développer une feature
```bash
make dev-run
# Code...
make test
make dev-run
```

### Tester en staging
```bash
make staging-full
# Vérifier...
make logs-all
```

### Déployer en prod
```bash
make test
make backup
make prod-full
# → Confirmation requise
make status
```

### Rollback d'urgence
```bash
make rollback-prod
```

---

## 🔧 Code Integration

```swift
// Config auto par env
let config = await ConfigurationManager.shared
let timeout = await config.getTimeout()
let nodes = await config.getNodes()

// Feature flags
if await config.isFeatureEnabled(.debugUI) {
    // Dev only
}
```

---

## 📚 Docs

- **MULTI_ENV.md** - Guide complet
- **WHATS_NEW.md** - Nouveautés
- **DEV_PROD_COMPLETE.md** - Récapitulatif

---

## ✅ Checklist Deploy Prod

- [ ] Tests passent
- [ ] Staging OK
- [ ] Backup créé
- [ ] `make prod-full`
- [ ] Confirmation
- [ ] Monitoring 1h

---

**3 environnements × 1 commande = Production ready ! 🎊**
