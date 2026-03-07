# TODO runtime MCP — `mascarade`

Last updated: 2026-03-07

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

## Reste ouvert

- [x] M-008 — Exposer un état synthétique MCP dans l'observabilité ops
  - AC: état `ready/degraded/failed` visible sans lire les logs bruts.

- [x] M-009 — Aligner la version de protocole MCP entre runtime principal et micro-serveurs restants
  - AC: une matrice explicite documente le support effectif.

- [ ] M-010 — Faire passer le boot réel du serveur sur une machine avec KiCad Python disponible
  - AC: `initialize` puis `tools/list` passent aussi sur le chemin host-native.

- [x] M-011 — Décider le statut final des micro-serveurs auxiliaires
  - AC: `component_database`, `kicad_tools` et `nexar_api` sont explicitement classés comme surfaces auxiliaires supportées.
