# CAD Stack

Stack Docker dédiée aux outils CAD/EDA du repo, séparée du `docker-compose.yml` principal généré par `./config`.

## Direction retenue

- `KiCad headless`: usage de `kicad-cli` dans l'image officielle `kicad/kicad:9.0`.
- `KiCad MCP`: le serveur du repo reste en `stdio`, ce qui colle au transport local recommandé par MCP aujourd'hui.
- `FreeCAD headless`: usage de `FreeCADCmd` pour l'exécution CLI/headless.
- `PlatformIO`: exécution CLI dans un conteneur Python minimal avec `platformio` installé via `pip`.

## Services

- `kicad-headless`: shell headless pour `kicad-cli`.
- `kicad-mcp`: image prête pour lancer le serveur MCP du repo en `stdio`.
- `freecad-headless`: shell headless pour `FreeCADCmd`.
- `platformio`: shell CLI pour `pio`.

## Usage rapide

```bash
./scripts/cad_stack.sh up
./scripts/cad_stack.sh doctor
./scripts/cad_stack.sh kicad-cli version
./scripts/cad_stack.sh freecad-cmd -c "import FreeCAD; print(FreeCAD.Version())"
./scripts/cad_stack.sh pio system info
./scripts/cad_stack.sh mcp
```

Le workspace monté dans les conteneurs est, par défaut, la racine du repo. Pour pointer ailleurs:

```bash
CAD_WORKSPACE_DIR=/chemin/vers/projets ./scripts/cad_stack.sh up
```

## Note MCP

La spec MCP actuelle recommande:

- `stdio` pour une communication locale entre processus.
- `Streamable HTTP` pour un serveur distant.

Le `kicad_mcp_server` présent dans le repo est encore `stdio-only`, donc cette stack le lance proprement comme processus conteneurisé. Si tu veux une exposition réseau MCP plus tard, il faudra ajouter un vrai transport `Streamable HTTP` au serveur, pas juste le mettre derrière un proxy.

## Sources

- KiCad CLI: https://docs.kicad.org/9.0/en/cli/cli.html
- MCP transports: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- FreeCAD headless: https://reqrefusion.github.io/FreeCAD-Documentation-html/wiki/Headless_FreeCAD.html
- PlatformIO Core install: https://docs.platformio.org/en/latest/core/installation/methods/installer-script.html
