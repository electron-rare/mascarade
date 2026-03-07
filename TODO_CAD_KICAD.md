# TODO - CAD / KiCad

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

- [ ] Ajouter un smoke operateur CAD dans la TUI
- [ ] Ajouter une doc courte sur les chemins plugins par OS
- [ ] Verifier si un `doctor` MCP dedie doit exister a cote du `doctor` plugins

## 4. Hors scope immediat

- [ ] Integrer la stack CAD dans le `docker-compose.yml` principal
- [ ] Exposer le serveur MCP KiCad sur un transport HTTP reseau
- [ ] Ajouter une UI cockpit pour piloter la stack CAD
