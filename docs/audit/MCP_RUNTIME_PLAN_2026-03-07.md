# Plan runtime MCP — `mascarade`

Last updated: 2026-03-07

## Objectif

Faire de `finetune/kicad_mcp_server` le serveur MCP KiCad réellement supporté par le workspace local.

## Cibles de sortie

- démarrage STDIO sans crash
- écriture uniquement dans des répertoires user-writable
- découverte minimale des libs KiCad même sans `sym-lib-table` / `fp-lib-table`
- classification claire des serveurs `kicad_kic_ai` en `live` ou `demo-only`

## Décisions retenues

- Le serveur de référence est `finetune/kicad_mcp_server`.
- Le transport de référence est `stdio`.
- Les MCP mock/demo restent hors chemin de production par défaut.
- `Kill_LIFE` consomme ce runtime via un launcher local, il ne possède pas son propre serveur MCP.

## Exécution

### Phase 1 — Hygiène runtime

1. Garantir un `KICAD_MCP_DATA_DIR` writable pour les données locales.
2. Vérifier que les logs/runtime tombent sous un `HOME` maîtrisé.
3. Éviter toute dépendance à un préfixe install immuable type `/opt/kicad-mcp`.

### Phase 2 — Discovery KiCad

1. Charger les libs depuis `sym-lib-table` / `fp-lib-table` si présents.
2. En fallback, scanner les répertoires système et user connus.
3. Considérer l’absence totale de lib comme un état dégradé explicite.

### Phase 3 — Surface exposée

1. Garder `kicad_mcp_server` comme surface supportée.
2. Marquer `component_database` et `kicad_tools` comme `demo-only`.
3. Exiger un `NEXAR_TOKEN` pour toute activation crédible de `nexar_api`.

### Phase 4 — Vérification

1. Tests unitaires ciblés sur writable paths et fallback discovery.
2. Smoke test local via le launcher `Kill_LIFE`.
3. Journaliser les écarts restants dans `MCP_BACKLOG_2026-03-07.md`.
