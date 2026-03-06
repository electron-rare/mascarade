# Journal de Portage Mascarade

Ce document consigne les changements et constats techniques qui rendent `mascarade`
plus portable entre machines locales, VM et hôtes Docker hétérogènes.

Il complète le runbook ops et les snapshots de migration, sans les remplacer.

## Objectif

Rendre l'installation plus robuste quand l'environnement réel diverge de la
machine de référence:
- Docker démarré ou non
- permissions Docker valides ou non
- GPU NVIDIA présent mais non exploitable dans Docker
- services optionnels activés ou non
- machine locale vs VM cible

## Politique de portabilité retenue

- Ne pas bloquer tout le setup sur une hypothèse machine implicite.
- Préférer un fallback CPU sûr plutôt qu'un crash au démarrage quand la chaîne
  GPU Docker n'est pas valide.
- Distinguer clairement:
  - GPU détecté sur l'hôte
  - GPU réellement utilisable depuis Docker
- Produire des diagnostics exploitables avant d'échouer.

## Améliorations déjà intégrées

### 1. Démarrage Docker plus robuste

- `setup` annule proprement l'étape de démarrage si le daemon Docker n'est pas
  joignable via `/var/run/docker.sock`.
- Le message de sortie oriente explicitement vers un redémarrage Docker puis une
  relance avec `./setup --skip-deps` ou `docker compose up -d`.

Effet attendu:
- éviter un build/up partiel trompeur
- réduire le bruit dans les health checks quand Docker n'est pas prêt

### 2. Diagnostic Docker plus précis dans les prérequis

- `scripts/prereqs.sh` différencie désormais:
  - daemon Docker arrêté
  - absence de permissions utilisateur
- Le setup n'affiche plus "permission denied" comme cause par défaut quand le
  vrai problème est un daemon non démarré.

Effet attendu:
- rendre les actions correctives immédiates et adaptées

### 3. Génération compose fiabilisée

- Correction de la génération YAML dans `scripts/modules/ollama.sh` pour éviter
  l'erreur shell `ambiguous redirect` lors de l'émission du `healthcheck`.

Effet attendu:
- empêcher un échec de génération du `docker-compose.yml` sur un détail de
  quoting shell

### 4. Fallback GPU -> CPU pour les services IA locaux

- `generate-audio` et `comfyui` n'activent plus le mode GPU uniquement sur la
  base de `nvidia-smi`.
- L'activation GPU dépend maintenant de deux conditions:
  - GPU NVIDIA visible côté hôte
  - runtime NVIDIA réellement disponible dans Docker
- Si Docker ne peut pas exposer le GPU, la génération du compose bascule en CPU
  au lieu de produire un conteneur qui échoue avec:
  - `could not select device driver "nvidia"`

Effet attendu:
- démarrage stable sur machine incomplètement préparée
- même repo utilisable sur machine CPU, machine GPU incomplète ou machine GPU
  correctement configurée

## Validation minimale sur une nouvelle machine

### Hôte

- `docker --version`
- `docker compose version`
- `docker info`
- si un GPU NVIDIA est attendu:
  - `nvidia-smi`

### Docker GPU

Ne considérer le GPU Docker comme valide que si un test réel passe:

```bash
docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
```

La présence d'une carte NVIDIA ou de paquets CUDA n'est pas suffisante.

### Repo

```bash
cd /mascarade
./setup --with core,api,ops-console --yes
```

Ou avec génération audio:

```bash
cd /mascarade
./setup --with core,api,ops-console,generate-audio --yes
```

Validation:
- `docker compose ps`
- `curl -fsS http://127.0.0.1:8100/health`
- `curl -fsS http://127.0.0.1:3100/health`
- `curl -fsS http://127.0.0.1:9000/health | python3 -m json.tool` si
  `generate-audio` est activé

## Constat machine relevé pendant ce portage

Etat clarifié sur la machine de travail pendant cette session:
- Ubuntu `24.04.4`
- Docker `29.3.0`
- GPU hôte présent: `NVIDIA GeForce RTX 4090`
- driver hôte opérationnel en accès système direct:
  - `nvidia-smi` retourne `580.126.09`
  - CUDA visible côté hôte: `13.0`
- `ComfyUI` tourne déjà localement hors Docker sur cette machine
- modules noyau NVIDIA chargés en branche `580`
- paquets NVIDIA `550` et `580` encore présents en parallèle
- runtime Docker `nvidia` absent au moment du diagnostic
- `nvidia-ctk` non installé au moment du diagnostic

Rectification importante:
- l'erreur `Failed to initialize NVML: Unknown Error` a été observée depuis
  l'environnement sandboxé de travail, mais pas en accès système direct
- le problème réel bloquant le portage GPU n'était donc pas le driver hôte
  principal, mais l'absence d'intégration NVIDIA côté Docker

Conséquence:
- un GPU physique et un driver fonctionnel ne suffisent pas
- la condition déterminante pour le mode GPU Docker reste la validation réelle
  de `docker run --gpus all ... nvidia-smi`
- le fallback CPU doit rester la politique par défaut tant que cette validation
  Docker GPU n'est pas positive

## Suivi de la session GPU/Docker

Séquence établie pendant ce portage:
- reproduction de l'erreur Docker:
  - `could not select device driver "nvidia" with capabilities: [[gpu]]`
- confirmation que `generate-audio` démarre en CPU après fallback
- confirmation que la carte NVIDIA est bien visible côté hôte en accès direct
- isolement du blocage sur l'absence de `nvidia-container-toolkit`
- transmission à l'utilisateur de la procédure d'installation/configuration du
  toolkit NVIDIA pour Docker
- relance manuelle du `setup` par l'utilisateur après cette étape

Etat atteint ensuite:
- `nvidia-container-toolkit` installé
- runtime Docker `nvidia` enregistré
- `docker-compose.yml` régénéré avec `generate-audio` en mode GPU
- stack réalignée sur le compose courant via suppression des anciens orphelins
- services conservés dans la stack courante:
  - `core`
  - `api`
  - `generate-audio`
  - `ops-console`
- `core`, `api` et `ops-console` signalés `healthy` par Docker
- validation HTTP applicative complémentaire:
  - état initial: `core /health` -> `200 OK` avec `{"status":"ok","providers":[],"agents":15}`
  - après intégration `ollama`: `core /health` -> `200 OK` avec `{"status":"ok","providers":["ollama"],"agents":15}`
  - `api /health` -> `200 OK` avec remontée du statut `core`
  - `api /` -> sert bien l'interface web compilée
- `generate-audio` démarré avec accès CUDA visible depuis le conteneur:
  - `torch.cuda.is_available() == True`
  - `torch.cuda.device_count() == 1`
- correction applicative ajoutée dans l'image `generate-audio`:
  - pin explicite `transformers==4.41.2`
  - motivation: éviter l'installation d'une version `5.x` incompatible avec
    `audiocraft==1.3.0` et `torch==2.1.0+cu118`
- smoke test applicatif validé in-container:
  - `POST /generate` -> `200 OK`
  - `Content-Type: audio/wav`
  - `X-Audio-Engine: audiogen`
  - `X-Audio-Model: facebook/audiogen-medium`
  - `X-Audio-Device: cuda`
  - réponse binaire reçue: `32078` octets
- intégration `ollama` finalisée sans `open-webui`:
  - service `ollama` gardé dans le compose
  - pas de publication du port hôte `11434`
  - réutilisation en lecture des modèles système via
    `OLLAMA_HOST_MODELS_DIR=/usr/share/ollama/.ollama`
  - `ollama list` in-container remonte les mêmes modèles que le service hôte
  - validation applicative: `POST /send` sur `core` avec
    `provider=ollama`, `model=qwen2.5:14b` -> `200 OK`, réponse `"ok"`
- authentification activée:
  - `MASCARADE_API_KEY` désormais renseignée dans `.env`
  - `GET /health` reste public sur `core` et `api`
  - routes protégées validées en `401` sans header
  - routes protégées validées en `200` avec `Authorization: Bearer <token>`

Note d'observation:
- les `curl http://127.0.0.1:8100` lancés depuis l'environnement sandboxé de
  travail peuvent échouer même quand les ports sont bien bindés sur l'hôte
- le signal de vérité utilisé pour cette session est donc:
  - statut Docker
  - healthchecks Docker
  - logs des services
  - vérification CUDA in-container

Commande de validation retenue pour Docker GPU:

```bash
docker info --format '{{json .Runtimes}}'
sudo docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

Commandes de relance retenues pour la stack:

```bash
cd /ai/saisail/mascarade
./setup --with core,api,ops-console,generate-audio,ollama --yes
```

## Travail restant pour un portage GPU complet

Le portage GPU Docker est maintenant fonctionnel sur cette machine pour
`generate-audio`, et l'orchestration LLM locale est fonctionnelle via `ollama`.

Le travail restant devient:
- valider explicitement `comfyui` en mode Docker GPU si ce service doit être
  intégré à cette stack et pas seulement utilisé hors Docker
- optionnel: normaliser la pile driver sur une seule branche si le mélange
  `550`/`580` provoque de futures dérives
- optionnel: documenter le résultat final de la commande
  `docker run --rm --gpus all ... nvidia-smi` si elle est exécutée côté
  terminal utilisateur

Le comportement attendu à ce stade est désormais:
- services de base disponibles
- `generate-audio` utilisable en GPU
- `ollama` utilisable dans le réseau compose sans conflit avec le service hôte
- `core` et `api` répondent en HTTP
- diagnostics explicites si un autre service local retombe en CPU

## Documents liés

- `README.md`
- `docs/RUNBOOK_VM_OPS.md`
- `docs/MIGRATION_MACHINE.md`
- `docs/audit/REMEDIATION_BACKLOG_2026-03-05.md`
