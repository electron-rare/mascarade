# TODO - CAD / KiCad

Statut suite:
- type: `implemented-reference`
- source active: `../Kill_LIFE/specs/mcp_tasks.md`
- bridge local: `docs/EXECUTION_HUB.md`

Etat de reference au 7 mars 2026.

## 1. Livre

- [x] Sous-modules KiCad enregistres proprement dans le repo parent
- [x] Wrapper versionne `scripts/install_kicad_plugins.sh`
- [x] Commande `doctor` pour verifier les bundles installes
- [x] Stack CAD dediee via `scripts/cad_stack.sh`
- [x] Lancement MCP local via `./scripts/cad_stack.sh mcp`

## 2. Priorite immediate

- [x] Ajouter une section `CAD / KiCad` dans `./config`
- [x] Ajouter `--cad-plugins`, `--cad-doctor`, `--cad-stack` dans `./setup`
- [x] Afficher un recapitulatif CAD dans `./config`
- [x] Proposer les actions CAD en post-setup interactif

## 3. Priorite suivante

- [x] Ajouter un smoke operateur CAD dans la TUI
  - `./scripts/cad_stack.sh smoke` (doctor + doctor-mcp + plugins host)
  - `./setup --cad-smoke` (propose en post-setup quand la stack est demarree)
- [x] Ajouter une doc courte sur les chemins plugins par OS
  - `./scripts/install_kicad_plugins.sh paths [--kicad-version VER]`
  - Affiche Linux, macOS, Windows + chemin resolu courant
- [x] Verifier si un `doctor` MCP dedie doit exister a cote du `doctor` plugins
  - `./scripts/cad_stack.sh doctor-mcp` (build image, verifie node+entrypoint, handshake JSON-RPC initialize)

## 4. Hors scope immediat

- [x] Integrer la stack CAD dans le `docker-compose.yml` principal
  - 4 services (kicad-headless, kicad-mcp, freecad-headless, platformio) sous profile `cad`
  - Resource limits et network backend configures
- [x] Exposer le serveur MCP KiCad sur un transport HTTP reseau
  - `deploy/cad/mcp-http-bridge.js` : bridge HTTP ↔ MCP stdio
  - Endpoints: POST /mcp, GET /health, GET /tools
  - Port configurable via `KICAD_MCP_PORT` (defaut 8300)
  - `MCP_TRANSPORT=http` active le bridge, `stdio` reste le defaut
- [x] Ajouter une UI cockpit pour piloter la stack CAD
  - Page `/cad` dans crazy_life (commit `f9c024e`): FreeCAD + OpenSCAD runtime, KiCad MCP probe
  - Nav entry Integrations, smoke test parallèle, stack reference card
