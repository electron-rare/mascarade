# Docker Compose Migration Guide

## Vue d'ensemble

Mascarade a migré d'un système de génération monolithique de `docker-compose.yml` vers un système modulaire basé sur les profils natifs de Docker Compose. Cette migration permet de démarrer des sous-ensembles de services de façon granulaire, réduisant la consommation de ressources et accélérant les itérations de développement.

## Pourquoi cette migration ?

### Ancien système (génération conditionnelle)
- Un seul fichier `docker-compose.yml` généré par `./setup --profile <preset>`
- Tous les services du profil étaient inclus dans le YAML généré
- Impossible de démarrer seulement un sous-ensemble de services sans regénérer le fichier
- Complexité croissante avec 30+ services
- Difficile de tester/debugger des services spécifiques

### Nouveau système (profils natifs)
- Un seul fichier `docker-compose.yml` contient TOUS les services, chacun taggé avec un profil
- Sélection dynamique via `docker compose --profile <nom> up`
- Composition flexible : plusieurs profils peuvent être combinés
- Pas besoin de regénérer le fichier pour changer les services actifs
- Meilleure utilisation des ressources (démarre seulement ce dont tu as besoin)

## Profils disponibles

| Profil | Services | Cas d'usage |
|--------|----------|-------------|
| `core` | core, api, redis, postgres | **Requis** — Services essentiels de routage et orchestration |
| `observability` | grafana, prometheus, loki, tempo, promtail, otel-collector, blackbox-exporter, langfuse, clickhouse | Monitoring, métriques, logs, traces |
| `industrial` | agent-factory-cockpit, edge-proxy, ops-agent | Services industriels et cockpit opérationnel |
| `personal` | n8n, dify, firecrawl, mem0, litellm, qdrant | Outils IA personnels et workflow automation |
| `fine-tuning` | comfyui, ollama, tts, stt, generate-audio | Fine-tuning et génération de modèles IA |

## Guide de migration

### Étape 1 : Sauvegarder votre configuration actuelle

```bash
cd /ai/saisail/mascarade  # Ou votre chemin d'installation

# Sauvegarder le docker-compose.yml actuel
cp docker-compose.yml docker-compose.yml.backup

# Sauvegarder le .env actuel
cp .env .env.backup

# Noter votre profil actuel
grep -E "^# .*profile" docker-compose.yml || echo "Pas de profil détecté"
```

### Étape 2 : Arrêter les services existants

```bash
# Arrêter proprement tous les services
docker compose down

# Vérifier qu'aucun conteneur ne tourne
docker compose ps
```

### Étape 3 : Mettre à jour votre installation

```bash
# Si vous utilisez git
git pull origin main

# Si vous avez des modifications locales, utilisez stash
git stash
git pull origin main
git stash pop
```

### Étape 4 : Régénérer docker-compose.yml avec les profils

Le nouveau système est maintenant activé par défaut. Le script `./setup` génère automatiquement un `docker-compose.yml` complet avec tous les services taggés par profil.

**Option A : Régénération interactive (recommandée)**

```bash
./setup
# Sélectionnez les services dont vous avez besoin
# Le script génère automatiquement le docker-compose.yml avec les profils appropriés
```

**Option B : Régénération non-interactive**

```bash
# Générer le fichier avec tous les services (sans démarrer)
./setup --yes --no-start

# Vérifier que les profils sont bien présents
grep -A 2 "profiles:" docker-compose.yml | head -20
```

### Étape 5 : Vérifier le nouveau fichier docker-compose.yml

```bash
# Vérifier la syntaxe
docker compose config > /dev/null && echo "✓ Syntaxe valide" || echo "✗ Erreur de syntaxe"

# Vérifier que les profils sont présents
grep -c "profiles:" docker-compose.yml
# Devrait afficher 30+ (un par service)

# Lister tous les services disponibles
docker compose config --services | sort

# Vérifier les services du profil core
docker compose config --profile core --services | sort
# Devrait afficher : api, core, postgres, redis
```

### Étape 6 : Démarrer vos services avec les profils

#### Migration depuis `--profile minimal`
```bash
# AVANT (ancien système)
./setup --profile minimal
docker compose up -d

# APRÈS (nouveau système)
docker compose --profile core up -d
```

#### Migration depuis `--profile standard`
```bash
# AVANT (ancien système)
./setup --profile standard
docker compose up -d

# APRÈS (nouveau système)
docker compose --profile core --profile observability up -d
```

#### Migration depuis `--profile full`
```bash
# AVANT (ancien système)
./setup --profile full
docker compose up -d

# APRÈS (nouveau système)
docker compose --profile core --profile observability --profile industrial --profile personal up -d
```

### Étape 7 : Vérifier le bon fonctionnement

```bash
# Vérifier que les services sont démarrés
docker compose ps

# Vérifier la santé du profil core
bash scripts/health-checks/core.sh

# Si vous utilisez observability
bash scripts/health-checks/observability.sh

# Si vous utilisez industrial
bash scripts/health-checks/industrial.sh

# Tester l'API
curl http://localhost:3100/health
# Devrait retourner : {"status":"ok"}

# Tester le Core
curl http://localhost:8100/health
# Devrait retourner : {"status":"healthy","version":"..."}
```

## Workflows courants

### Démarrage minimal (développement rapide)
```bash
# Seulement les services essentiels (core, api, redis, postgres)
docker compose --profile core up -d

# Logs en temps réel
docker compose --profile core logs -f core api
```

### Stack de monitoring complète
```bash
# Core + observability
docker compose --profile core --profile observability up -d

# Accéder à Grafana
open http://localhost:3001
```

### Production complète
```bash
# Tous les profils principaux
docker compose \
  --profile core \
  --profile observability \
  --profile industrial \
  --profile personal \
  up -d
```

### Arrêt sélectif
```bash
# Arrêter seulement le profil observability
docker compose stop grafana prometheus loki tempo promtail otel-collector blackbox-exporter

# Ou arrêter tous les services
docker compose down
```

### Rebuild et restart
```bash
# Rebuild un service spécifique
docker compose --profile core build core

# Restart avec le nouveau build
docker compose --profile core up -d core
```

## Troubleshooting

### Problème : "no configuration file provided"

**Cause** : Le fichier docker-compose.yml n'existe pas ou n'est pas au bon endroit.

**Solution** :
```bash
# Vérifier le fichier
ls -la docker-compose.yml

# Régénérer si nécessaire
./setup --yes --no-start

# Vérifier le contenu
head -50 docker-compose.yml
```

### Problème : Les services ne démarrent pas

**Cause** : Le profil n'a pas été spécifié ou mauvais profil.

**Solution** :
```bash
# Vérifier les profils disponibles pour un service
docker compose config --services

# Vérifier le profil d'un service spécifique
grep -A 2 "^  core:" docker-compose.yml

# Démarrer avec le bon profil
docker compose --profile core up -d
```

### Problème : "unknown shorthand flag: 'p' in -p"

**Cause** : Confusion entre `docker-compose` (v1, obsolète) et `docker compose` (v2).

**Solution** :
```bash
# Vérifier la version de Docker Compose
docker compose version
# Devrait afficher : Docker Compose version v2.x.x

# Ne JAMAIS utiliser docker-compose (v1)
# Toujours utiliser docker compose (v2, sans tiret)
```

### Problème : Services d'autres profils démarrent

**Cause** : Des dépendances entre services peuvent démarrer des services d'autres profils.

**Solution** :
```bash
# Vérifier quels services tournent
docker compose ps

# Arrêter les services non désirés
docker compose stop <service-name>

# Ou arrêter tout et redémarrer proprement
docker compose down
docker compose --profile core up -d
```

### Problème : Variables d'environnement manquantes

**Cause** : Le fichier `.env` n'est pas à jour ou manquant.

**Solution** :
```bash
# Vérifier le fichier .env
cat .env | head -20

# Régénérer avec ./setup si nécessaire
./setup --yes --no-start

# Vérifier les variables requises
grep "CORE_PORT\|API_PORT\|REDIS_HOST" .env
```

### Problème : Impossible de se connecter à un service

**Cause** : Le service n'est pas dans le profil actif ou n'est pas démarré.

**Solution** :
```bash
# Vérifier que le service tourne
docker compose ps | grep <service-name>

# Vérifier le profil du service
grep -B 1 "^  <service-name>:" docker-compose.yml | grep profiles

# Démarrer avec le bon profil
docker compose --profile <profil> up -d

# Vérifier les logs du service
docker compose logs <service-name>
```

## Retour à l'ancien système (si nécessaire)

Si tu rencontres des problèmes bloquants avec le nouveau système, tu peux temporairement revenir à l'ancien mode de génération :

```bash
# Utiliser le mode legacy
./setup --legacy-generation --profile standard

# Note : Cette option est DEPRECATED et sera supprimée dans une future version
# Utilise-la seulement temporairement pour débugger
```

**Important** : Le mode `--legacy-generation` est déprécié et sera retiré. Il est fortement recommandé de migrer vers le système de profils natifs.

## Avantages du nouveau système

### Économie de ressources
```bash
# AVANT : Démarrer 20+ services même pour tester une modif de l'API
./setup --profile full
docker compose up -d
# RAM utilisée : ~16 GB

# APRÈS : Démarrer seulement les 4 services essentiels
docker compose --profile core up -d
# RAM utilisée : ~2 GB
```

### Itération rapide
```bash
# AVANT : Régénérer le fichier pour changer les services
./setup --profile minimal
docker compose down
docker compose up -d
# Temps : ~5 minutes

# APRÈS : Changer de profil instantanément
docker compose down
docker compose --profile core --profile observability up -d
# Temps : ~30 secondes
```

### Flexibilité
```bash
# Composer exactement la stack dont tu as besoin
docker compose \
  --profile core \
  --profile observability \
  --profile fine-tuning \
  up -d

# Ajouter un profil à chaud
docker compose --profile personal up -d

# Retirer un profil
docker compose stop n8n dify firecrawl mem0 litellm qdrant
```

## Scripts de health check

Le nouveau système inclut des scripts de validation pour chaque profil :

```bash
# Vérifier le profil core
bash scripts/health-checks/core.sh

# Vérifier le profil observability
bash scripts/health-checks/observability.sh

# Vérifier le profil industrial
bash scripts/health-checks/industrial.sh
```

## Tests E2E

Des scripts de test end-to-end sont disponibles pour valider les profils :

```bash
# Tester le profil core (démarre, vérifie, arrête)
bash scripts/test-core-profile.sh

# Tester core + observability
bash scripts/test-observability-profile.sh
```

## Références

- **Documentation profils** : [README.md](../README.md#docker-compose-profiles)
- **Health checks** : `scripts/health-checks/*.sh`
- **Tests E2E** : `scripts/test-*-profile.sh`
- **Génération** : `scripts/compose.sh`
- **Mappings profils** : `scripts/services.sh` (variable `SVC_PROFILES`)

## Support

Si tu rencontres des problèmes non couverts par ce guide :

1. Vérifier les logs : `docker compose logs <service-name>`
2. Vérifier la santé : `bash scripts/health-checks/<profile>.sh`
3. Vérifier la configuration : `docker compose config`
4. Consulter les issues GitHub du projet
5. Créer une issue avec les détails de l'erreur et les logs pertinents

## Contribution

Si tu trouves des cas d'usage ou problèmes non documentés, n'hésite pas à contribuer à ce guide via une pull request.
