# TODO — Finalisation VM

Etat relu le `9 mars 2026` sur `photon-machine`.

Ce fichier couvre uniquement la VM et la stack runtime de `/mascarade`.
Le pilotage central multi-repo vit dans `docs/EXECUTION_HUB.md`.

## Pilotage multi-machine

- [x] Le hub d'execution sait maintenant filtrer les lots par `Portee`:
  - `global`
  - `machine:<hostname>`
  - `cap:<capability>`
- [x] Le profil local de `photon-machine` est declare dans `docs/MACHINE_PROFILES.json`.
- [x] Declarer des profils logiques pour les prochaines machines utiles dans `docs/MACHINE_PROFILES.json`:
  - `net-runner`
  - `kicad-runner`
  - `nexar-runner`
- [x] Une matrice de dispatch multi-machine existe via `scripts/machine_lot_matrix.sh`.
- [ ] Quand une autre machine sera prete, utiliser `scripts/current_machine_context.sh` puis `scripts/chain_next_lot.sh --machine <nom>` pour reprendre les lots delegues.

## Surface runtime de reference

| Surface | Compose / container | Bind retenu | Statut |
| --- | --- | --- | --- |
| Ops Console | main compose / `mascarade-ops-console` | LAN `:80` | OK |
| Dify Web | `deploy/dify.machine.yml` / `mascarade-dify-web` | LAN `:3500` | OK |
| Dify API | `deploy/dify.machine.yml` / `mascarade-dify-api` | LAN `:5001` | OK |
| Mascarade API | main compose / `mascarade-api` | loopback `:3100` | OK |
| Mascarade Core | main compose / `mascarade-core` | loopback `:8100` | OK |
| Grafana | main compose / `mascarade-grafana` | loopback `:3001` | OK |
| Prometheus | main compose / `mascarade-prometheus` | loopback `:9090` | OK |
| Ollama | main compose / `mascarade-ollama` | loopback `:11434` | OK / optionnel |

Notes:
- `ops-console` sur `:80` via le main compose est maintenant la surface standard. `edge-proxy` n'est plus le chemin principal par defaut pour cette machine.
- `core`, `api`, `grafana`, `prometheus`, `ollama`, `qdrant`, `n8n` et `studio-ai-gateway` restent sur loopback sauf besoin explicite.
- Dify reste sur le compose dedie `deploy/dify.machine.yml`, avec `DIFY_MACHINE_HOST` comme source unique des URLs publiees.

## Ce qui est verrouille

- [x] `./setup` ne remappe plus `ops-console` vers `edge-proxy`.
- [x] `ops-console` main compose reprend `:80` et sert la surface operateur de la machine.
- [x] L'overlay `photon-machine` est separe dans `.env.machine.local(.example)`.
- [x] La page Ops Console applique un filtrage LAN et des cartes loopback basees sur verification locale.
- [x] `./setup` / `write_env_file()` ne laissent plus sortir un `.env` runtime avec `MASCARADE_API_KEY` vide si `core` ou `api` sont selectionnes.

## Stack personnelle legere

- [x] `deploy/personal.machine.yml` est la source de verite pour la stack perso locale.
- [x] Le cockpit perso est precharge et versionne via `deploy/personal-seed/*.json`.
- [x] Les scripts `scripts/personal_stack_reconcile.sh`, `scripts/personal_stack_verify.sh` et `scripts/personal_stack_lots.sh` rejouent et verifient la wave 1 sans refaire le seed a la main.
- [x] Les checks `Healthchecks` sont laisses sans cron placeholder tant qu'aucun job reel n'est cable.
- [ ] Cabler les premiers jobs reels vers `mascarade-ops`, `mascarade-jobs`, `mascarade-watch` et les checks `Healthchecks`.
- [ ] Preparer la phase 2 distante (`SearXNG`, `Paperless-ngx`, `Karakeep`) et l'ajouter a l'Ops Console sans alourdir `photon-machine`.

## Backlog prioritaire restant

### Securite / secrets operateur

- [ ] Renseigner seulement les secrets reellement utiles sur cette machine:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `NOTION_API_KEY`
- [ ] Garder les secrets machine hors des fichiers versionnes:
  - `.env`
  - `.env.machine.local`

### Tooling opt-in

- [ ] Installer `Docling` dans le venv tools uniquement si un flux local de parsing documentaire le demande.
- [ ] Installer `openai-whisper` dans le venv tools uniquement si une transcription locale hors conteneur devient necessaire.

### Reseau / exposition

- [ ] Revalider la regle hote/`DOCKER-USER` pour `80/tcp`, `3500/tcp` et `5001/tcp` apres tout changement reseau.
- [ ] Si une exposition publique TLS redevient voulue, definir un chemin explicite `edge-proxy` ou reverse proxy tiers au lieu de rouvrir des binds au hasard.

## Deplace hors de ce fichier

- Observabilite et cockpit ops: `TODO_COCKPIT_OPS.md`
- Backlog cockpit/release canonique: `/mascarade/opt/repos/crazy_life/plan.md`
- Backlog MCP canonique: `/mascarade/opt/repos/kill_life/specs/mcp_tasks.md`

## Fichiers de reference

```text
/mascarade/docs/EXECUTION_HUB.md
/mascarade/docs/PERSONAL_STACK_MACHINE.md
/mascarade/docs/MULTI_MACHINE_EXECUTION.md
/mascarade/docs/MACHINE_PROFILES.json
/mascarade/docs/RUNBOOK_VM_OPS.md
/mascarade/.env.example
/mascarade/.env.machine.local.example
```
