# Plan runtime MCP — `mascarade`

Last updated: 2026-03-14

Document d'audit mis à jour après implémentation du runtime MCP.

## Objectif

Garder `finetune/kicad_mcp_server` comme serveur MCP KiCad réellement supporté par le workspace local, tout en reclassant correctement les micro-serveurs `kicad_kic_ai`.

## État actuel

- le serveur KiCad principal démarre via `Kill_LIFE/tools/hw/run_kicad_mcp.sh`
- le runtime écrit dans un data dir writable sous `.cad-home/kicad-mcp`
- le fallback hôte -> conteneur fonctionne sur la machine auditée
- le smoke `initialize -> tools/list -> resources/list -> prompts/list` passe
- `component_database` et `kicad_tools` ne sont plus des mocks, mais des micro-serveurs réels désormais supportés comme surfaces auxiliaires
- la pile MCP locale converge désormais sur `2025-03-26`
- l'observabilité synthétique MCP est exposée via `/api/ops/summary`
- la revue `registry-first` contrôle maintenant aussi les minima `startup_timeout_sec` pour les launchers locaux lents

## Décisions retenues

- le serveur de référence reste `finetune/kicad_mcp_server`
- le transport de référence reste `stdio`
- le point d'entrée opérateur reste côté `Kill_LIFE`
- les micro-serveurs `kicad_kic_ai` sont supportés comme surfaces auxiliaires, sans être promus au rang de runtime principal
- la discovery future suit maintenant une politique `registry-first`:
  - `official` quand un connecteur vendor/registry officiel existe;
  - `community-valid` quand on dépend d'un upstream public crédible mais non officiel;
  - `local-only` pour les launchers et surfaces métier propres au triptyque `mascarade` / `Kill_LIFE` / `agent-factory-cockpit`
- la matrice opératoire détaillée vit désormais dans `docs/audit/MCP_REGISTRY_FIRST_2026-03-14.md`
- les launchers locaux lents gardent des timeouts explicites dans la config Codex cible:
  - `validate-specs` = `20s`
  - `openscad` = `30s`
  - `freecad` = `45s`
- le sandbox `workspace-write` actuel peut auditer `~/.codex/config.toml`, mais pas l'écrire; toute correction directe passe donc par une shadow config validée puis une application hors sandbox

## Travail absorbé

### Phase 1 — Hygiène runtime

1. Garantir un `KICAD_MCP_DATA_DIR` writable
2. Faire tomber les logs/runtime sous un `HOME` maîtrisé
3. Éviter les écritures par défaut dans `/opt/kicad-mcp`

### Phase 2 — Discovery KiCad

1. Charger des librairies KiCad réelles
2. Ajouter un fallback praticable même sans tables KiCad complètes
3. Faire fonctionner le runtime sur conteneur KiCad v10 quand l'hôte n'expose pas `pcbnew`

### Phase 3 — Micro-serveurs auxiliaires

1. Remplacer le mock `component_database` par une source réelle locale + cache KiCad v10
2. Remplacer le mock `kicad_tools` par des analyses réelles de fichiers KiCad
3. Clarifier `nexar_api`: mode démo explicite, mode live encore à valider

### Phase 4 — Vérification

1. Smoke versionné côté consommateur
2. Sync/versioning du cache KiCad v10
3. Mesures de cold start pour les MCP auxiliaires

## Ce qu'il reste

1. Revalider le chemin host-native sur une machine avec `pcbnew`
2. Valider `nexar_api` en mode live avec `NEXAR_TOKEN`
3. Garder la séparation entre runtime principal et surfaces auxiliaires supportées
4. Garder `scripts/data/mcp_registry_inventory.json` synchronisé avant tout ajout de serveur MCP dans la doc ou la config locale
5. Appliquer hors sandbox la shadow config Codex validée sur `~/.codex/config.toml`
