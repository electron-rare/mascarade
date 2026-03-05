# Architecture et etat machine/projet

Date du rapport: 2026-03-05 09:01:37 UTC
Perimetre: machine `photon-machine` + projet `/mascarade`

## 1) Resume executif

- Machine VMware Photon OS 5.0, 4 vCPU, 6.8 GiB RAM, swap 4 GiB.
- Stack fortement orientee Docker (39 conteneurs inventoriees, 27 actifs au snapshot).
- Pression ressource notable:
  - load average elevee (pic observe jusqu'a `71.13` en 15 min).
  - swap tres utilisee (`3.6/4.0 GiB`, ~90%).
- Disque racine a `74%` (encore sous seuil critique, mais volume Docker important).
- Cote projet `mascarade`: architecture modulaire propre (setup -> modules -> compose/.env), plus bootstrap explicite du frontend `ops-console-v3`.
- Nettoyage effectue: purge des caches Python/tests (`__pycache__`, `.pytest_cache`) dans le workspace.

## 2) Architecture machine

### 2.1 Socle systeme

- Hostname: `photon-machine`
- OS: `VMware Photon OS/Linux`
- Kernel: `6.1.159-1.ph5-esx`
- Virtualisation: VMware (`VMware7,1`)
- CPU logiques: `4`

### 2.2 Reseau

- Interface principale: `eth0` -> `192.168.0.119/24`
- Exposition principale:
  - `22/tcp` (SSH)
  - `80/tcp` (reverse proxy/cockpit via docker-proxy)
- Le reste des services est majoritairement borne en `127.0.0.1` (pattern sain pour limiter l'exposition LAN).

### 2.3 Services systemd critiques

Etat: OK au moment du snapshot

- `docker.service`: active
- `sshd.service`: active
- `systemd-resolved.service`: active
- `systemctl --failed`: 0 unite en echec

### 2.4 Etat ressources

- RAM: `4.2/6.8 GiB` utilisee, cache 1.5 GiB
- Swap: `3.6/4.0 GiB` (alerte performance)
- Disque `/`: `74%` (175G/246G)
- Docker footprint:
  - Images: `92.76GB` (reclaimable 60.35GB)
  - Volumes: `63.55GB`
  - Build cache: `2.006GB`

## 3) Topologie containers (machine)

### 3.1 Inventaire global

- Conteneurs totaux: `39`
- Conteneurs actifs: `27`

### 3.2 Observations sante

Logs systeme recents (`journalctl -p err`) montrent des alertes recurrentes sur des conteneurs en etat degrade/exited:

- `zacus-ollama` (Exited)
- `zacus-open-webui` (Exited 137)
- `zacus-pinchtab` (Exited 137)
- `ops-console` (degrade historique)
- periodes d'"unhealthy" sur `zacus-studio-ai-gateway`, `zacus-redis`, `zacus-qdrant`, `zacus-postgres`, `zacus-zeroclaw`, `zacus-continue-ai`

Interpretation: la machine heberge plusieurs stacks en parallele (`mascarade`, `docker-studio-ai`, `zacus-stack`, `tools`), ce qui augmente la contention CPU/RAM/IO.

## 4) Architecture projet Mascarade

## 4.1 Structure (niveau 1-2)

Repertoire racine: `/mascarade`

Blocs majeurs:

- `core/`: backend Python (FastAPI, orchestration, providers)
- `api/`: gateway API (Hono/TS)
- `scripts/`: coeur de l'orchestration setup/config/deploy
- `scripts/modules/`: definition compose/config par service
- `deploy/`: Dockerfiles + assets de deploiement
- `docs/`: documentation et donnees d'architecture
- `setup`, `config`, `update`: points d'entree operatoires
- `opt/docker-studio-ai/`: source locale frontend/cockpit externe (utilisee au setup)

## 4.2 Pipeline setup (comportement)

Pipeline principal observe dans `setup`:

1. Selection services
2. Resolution dependances
3. Verification prerequis
4. Configuration `.env`
5. Generation `docker-compose.yml`
6. Installation dependances locales
7. Demarrage stack
8. Installation assets repo (skills/LLMs selon options)

Fonctions pivots:

- `collect_module_configs`
- `generate_compose`
- `write_env_file`

## 4.3 Frontend/Cockpit

- Le setup impose desormais la presence de `ops-console-v3` (plus de fallback silencieux legacy).
- Emplacements resolus:
  - `/opt/docker-studio-ai/tools/dev/ops-console-v3`
  - `$REPO_DIR/opt/docker-studio-ai/tools/dev/ops-console-v3`
  - autres chemins derives de l'environnement
- Bypass explicite possible: `ALLOW_LEGACY_OPS_CONSOLE=true`

## 4.4 Catalogue services Mascarade (etat du code)

Services declares (19):

- coeur: `core`, `api`
- outils: `litellm`, `n8n`, `langfuse`, `dify`, `clickhouse`, `comfyui`, `tts`, `stt`, `generate-audio`
- infra: `ollama`, `open-webui`, `ops-console`, `redis`, `postgres`, `qdrant`, `grafana`, `prometheus`

Evolutions recentes prises en compte:

- `tts` multi-moteur
- `stt` multi-moteur (incluant `whisperx`)
- `generate-audio` converti en vrai service de generation audio (AudioGen/MusicGen)

## 4.5 Dependances de services

Dependances explicites (extrait):

- `api -> core`
- `litellm -> redis`
- `n8n -> postgres`
- `langfuse -> postgres + clickhouse`
- `dify -> postgres + redis`
- `open-webui -> ollama`

Source de verite: `scripts/services.sh`
Donnee consolidee: `docs/dependency_tree.json`

## 5) Nettoyage effectue (cette passe)

Actions appliquees:

- Suppression des caches Python/tests:
  - `__pycache__`
  - `.pytest_cache`

Impact observe:

- Taille `/mascarade` apres nettoyage: `27M`
- Taille `/mascarade/core`: `252K`
- Taille `/mascarade/core/.venv`: `107M`

Note: les caches supprimes dans `.venv` sont regenerables automatiquement.

## 6) Risques et points d'attention

### Risque eleve

- Saturation memoire imminente (swap a ~90%) -> latence, kill OOM possibles, instabilite conteneurs.

### Risque moyen

- Co-habitation de plusieurs stacks lourdes sur 4 vCPU / 6.8 GiB.
- Inventaire images Docker tres lourd (dont images >3GB, et une image a 38.7GB).

### Risque bas

- Disque a 74%: acceptable court terme, a surveiller avec la croissance volumes/logs.

## 7) Plan de cleanup recommande (prochain run)

1. Rationaliser les stacks actives (ne laisser Up que la stack necessaire a l'instant T).
2. Nettoyer images non utilisees apres validation metier (`docker image prune -a`) pour recuperer de l'espace.
3. Purger build cache Docker (`docker builder prune`) regulierement.
4. Mettre des limites memoire CPU/RAM sur services non critiques (compose `deploy.resources`).
5. Ajouter un check automatique RAM+swap dans le healthcheck cockpit.
6. Eventuellement augmenter RAM VM a 12-16 GiB si multi-stack permanent.

## 8) Arbre de reference rapide

Machine:

- OS: Photon 5
- Runtime: Docker + systemd
- Reseau principal: 192.168.0.119
- Port public clef: 80/22

Projet Mascarade:

- entree: `setup`, `config`, `update`
- orchestration: `scripts/`
- modules services: `scripts/modules/`
- deploiement: `deploy/`
- backend: `core/` + `api/`
- donnees architecture: `docs/dependency_tree.json`

