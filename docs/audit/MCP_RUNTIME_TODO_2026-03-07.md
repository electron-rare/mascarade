# TODO runtime MCP — `mascarade`

Last updated: 2026-03-14

Format:

- `[ ]` non fait
- `[x]` fait

## Implémenté

- [x] M-001 — Utiliser un data dir writable pour la base JLCPCB locale
  - AC: plus d'écriture par défaut dans un préfixe immuable.

- [x] M-002 — Découvrir des libs KiCad réelles
  - AC: le runtime principal et les auxiliaires voient des symboles/footprints réels.

- [x] M-003 — Ajouter un smoke test STDIO versionné pour `kicad_mcp_server`
  - AC: un smoke test consommateur versionné existe côté `Kill_LIFE`.

- [x] M-004 — Corriger le chemin réel `NEXAR_TOKEN`
  - AC: le serveur `nexar_api` n'utilise plus un attribut d'auth incohérent.

- [x] M-005 — Remplacer les mocks auxiliaires par des backends réels
  - AC: `component_database` et `kicad_tools` ne se contentent plus de réponses simulées.

- [x] M-006 — Brancher les auxiliaires sur le conteneur KiCad v10
  - AC: les librairies symboles/footprints exportées sont exploitées via cache local.

- [x] M-007 — Indexer le catalogue auxiliaire
  - AC: `component_database` utilise un index SQLite persistant pour le cache symboles.

## Implemente apres la derniere mise a jour

- [x] M-008 — Exposer un état synthétique MCP dans l'observabilité ops
  - AC: `probeMcpRuntime()` dans `api/src/routes/ops.ts` avec cache TTL, statut `ready/degraded/failed` dans `/summary`.

- [x] M-009 — Aligner la version de protocole MCP entre runtime principal et micro-serveurs restants
  - AC: une matrice explicite documente le support effectif.

- [x] M-011 — Décider le statut final des micro-serveurs auxiliaires
  - AC: `component_database`, `kicad_tools` et `nexar_api` sont explicitement classés comme surfaces auxiliaires supportées.

- [x] M-012 — Formaliser les minima de bootstrap MCP local
  - AC: `scripts/data/mcp_registry_inventory.json` et `scripts/tui/mcp_registry_review.sh` signalent désormais `validate-specs<20`, `openscad<30` et `freecad<45`.

## Reste ouvert

- [ ] M-010 — Faire passer le boot réel du serveur sur une machine avec KiCad Python disponible
  - AC: `initialize` puis `tools/list` passent aussi sur le chemin host-native.

- [ ] M-013 — Appliquer hors sandbox la shadow config Codex validée
  - AC: `~/.codex/config.toml` porte `MASCARADE_DIR=/Users/electron/mascarade` pour `kicad`, `knowledge-base`, `github-dispatch`, `freecad`, `openscad`, plus `startup_timeout_sec=20/30/45` pour `validate-specs` / `openscad` / `freecad`.
