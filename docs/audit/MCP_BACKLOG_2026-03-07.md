# Backlog MCP — 2026-03-07

## Résumé

Ce backlog reflète l'état MCP après implémentation, pas seulement l'état de l'audit initial.

Source de vérité opérateur:

- `Kill_LIFE/docs/MCP_SETUP.md`
- `Kill_LIFE/docs/MCP_SUPPORT_MATRIX.md`
- `Kill_LIFE/specs/mcp_tasks.md`

## État courant

- un runtime KiCad principal est réellement opérable via `Kill_LIFE/tools/hw/run_kicad_mcp.sh`
- `validate-specs` existe réellement et n'est plus une promesse cassée
- `notion` et `github-dispatch` existent désormais comme serveurs MCP locaux versionnés
- `component_database` et `kicad_tools` ne sont plus des mocks
- `nexar_api` est cohérent côté token, mais son mode live reste à valider
- la pile MCP locale converge désormais sur `2025-03-26`
- un probe synthétique est exposé via `/api/ops/summary`

## Inventaire actuel

| Surface MCP | Emplacement | État observé | Statut |
| --- | --- | --- | --- |
| `kicad` | `Kill_LIFE/tools/hw/run_kicad_mcp.sh` -> `mascarade/finetune/kicad_mcp_server` | runtime principal, smoke OK, fallback conteneur OK | Supporté |
| `validate-specs` | `Kill_LIFE/tools/validate_specs.py --mcp` | CLI + MCP réels | Supporté |
| `notion` | `Kill_LIFE/tools/run_notion_mcp.sh` -> `mascarade/core/mascarade/integrations/notion.py` | handshake OK, erreurs structurées sans secret | Supporté |
| `github-dispatch` | `Kill_LIFE/tools/run_github_dispatch_mcp.sh` -> `mascarade/core/mascarade/integrations/github_dispatch.py` | handshake OK, allowlist + statut local structurés | Supporté |
| `component_database` | `mascarade/finetune/kicad_kic_ai/mcp_servers/component_db.py` | file-backed, cache KiCad v10, index SQLite | Supporté |
| `kicad_tools` | `mascarade/finetune/kicad_kic_ai/mcp_servers/kicad_tools.py` | analyses réelles schéma/PCB/BOM/footprints | Supporté |
| `nexar_api` | `mascarade/finetune/kicad_kic_ai/mcp_servers/nexar.py` | mode démo explicite, mode live non encore validé | Supporté |
| `huggingface` | `https://huggingface.co/mcp` (remote HTTP SSE) | token auth via `HUGGINGFACE_API_KEY`, OAuth login via `?login` | Supporté |
| `kicad-sch-mcp` | docs historiques | pas de chemin supporté dans ce workspace | Non supporté |

## Résolu depuis l'audit initial

### MCP-001 — `validate-specs`

- Résolu
- `Kill_LIFE/mcp.json` ne référence plus aucun chemin absent

### MCP-002 — Chemin KiCad MCP supporté

- Résolu
- `Kill_LIFE` pousse un seul chemin opérateur supporté

### MCP-003 — Boot `kicad_mcp_server`

- Résolu côté runtime supporté
- le serveur démarre via fallback conteneur quand l'hôte n'expose pas `pcbnew`

### MCP-004 — Chargement des libs KiCad

- Résolu côté runtime supporté et auxiliaires
- les librairies réelles sont chargées ou exportées via le cache KiCad v10

### MCP-006 — MCP mockés

- Résolu en partie
- `component_database` et `kicad_tools` ne sont plus mockés
- leur statut est désormais `supporté` comme surfaces auxiliaires

### MCP-007 — `nexar_api`

- Résolu en partie
- le chemin `NEXAR_TOKEN` est propre
- le mode live réel reste à valider

### MCP-009 — outillage de test MCP

- Résolu
- un smoke versionné existe et passe sur la machine auditée

## Résolu après implémentation complémentaire

### B-001 — Aligner les protocoles MCP

- Résolu
- le runtime KiCad principal, `validate-specs` et les micro-serveurs auxiliaires convergent désormais sur `2025-03-26`

### B-002 — Ajouter une observabilité MCP synthétique

- Résolu
- `/api/ops/summary` expose maintenant un bloc `mcp` avec statut, runtime, protocole et compteurs

### B-004 — Implémenter les MCP `notion` et `github-dispatch`

- Résolu
- `Kill_LIFE/mcp.json` référence désormais les deux serveurs locaux et leurs launchers versionnés

## Backlog restant

### B-003 — Rejouer la validation host-native

- Priorité: moyenne
- Problème: la machine auditée valide surtout le chemin conteneur.
- Sortie attendue:
  1. smoke vert sur machine avec `pcbnew`
  2. absence de dérive entre host et conteneur

### B-005 — Valider le mode live de `nexar_api`

- Priorité: moyenne
- Problème: l'usage sans token reste volontairement en démo.
- Sortie attendue:
  1. test live avec `NEXAR_TOKEN`
  2. distinction nette entre données live et démo
