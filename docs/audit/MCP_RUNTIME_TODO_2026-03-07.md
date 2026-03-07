# TODO runtime MCP — `mascarade`

Last updated: 2026-03-07

Format:

- `[ ]` non fait
- `[x]` fait

## Sprint actif

- [x] M-001 — Utiliser un data dir writable pour la base JLCPCB locale
  - AC: plus d’écriture par défaut dans un préfixe immuable.
- [x] M-002 — Découvrir des libs KiCad sans `sym-lib-table` / `fp-lib-table`
  - AC: au moins une découverte filesystem fallback existe côté symboles et footprints.
- [x] M-003 — Désactiver les MCP mockés par défaut
  - AC: `component_database` et `kicad_tools` ne sont plus présentés comme prod-ready.
- [x] M-004 — Corriger le chemin réel `NEXAR_TOKEN`
  - AC: le serveur `nexar_api` n’utilise plus un attribut d’auth incohérent.

## À faire ensuite

- [x] M-005 — Ajouter un smoke test STDIO versionné pour `kicad_mcp_server`
  - AC: un smoke test versionné existe côté consommateur.
- [ ] M-006 — Exposer un état synthétique MCP dans l’observabilité ops
  - AC: état `ready/degraded/failed` visible sans lire les logs bruts.
- [ ] M-007 — Aligner la version de protocole MCP entre runtime principal et micro-serveurs restants
  - AC: une matrice explicite documente le support effectif.
- [ ] M-008 — Faire passer le boot réel du serveur sur une machine avec KiCad Python disponible
  - AC: `initialize` puis `tools/list` passent sans dépendre d’un container legacy.
  - Blocage actuel: `pcbnew` est absent sur l’hôte audité.
