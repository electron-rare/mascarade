# CAD Stack

Stack Docker dédiée aux outils CAD/EDA du repo, séparée du `docker-compose.yml` principal généré par `./config`.

## Pilotage via la TUI Mascarade

Le flux recommandé est maintenant:

```bash
./config
```

Puis sélectionner `CAD / KiCad` pour régler:

- `KICAD_VERSION`
- `KICAD_PLUGIN_DIR`
- `CAD_WORKSPACE_DIR`
- `CAD_INSTALL_BUNDLES`

Ensuite, depuis le setup principal:

```bash
./setup --cad-plugins --cad-doctor --cad-stack
```

En interactif, `./setup` propose aussi ces actions en post-setup sans les activer par défaut.

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

## Helpers locaux versionnés dans `mascarade`

Les wrappers locaux ne vivent plus dans les sous-modules KiCad. Les entrées partagées sont maintenant:

```bash
./scripts/install_kicad_plugins.sh list
./scripts/install_kicad_plugins.sh install fabrication-toolkit --yes
./scripts/install_kicad_plugins.sh install kic-ai --yes
./scripts/install_kicad_plugins.sh doctor all
./scripts/cad_stack.sh mcp
```

Par défaut, l'install cible:

```text
~/.config/kicad/9.0/scripting/plugins
```

Tu peux surcharger le répertoire cible:

```bash
./scripts/install_kicad_plugins.sh install all \
  --plugin-dir /chemin/custom/plugins \
  --yes
```

Vérifier que KiCad verra bien les bundles installés:

```bash
./scripts/install_kicad_plugins.sh doctor all
./scripts/install_kicad_plugins.sh doctor kic-ai --plugin-dir /chemin/custom/plugins
```

Le `doctor` vérifie:

- le dossier bundle ciblé
- `metadata.json`
- l'identifiant plugin attendu
- le répertoire `plugins/`
- le point d'entrée `plugins/__init__.py`

Le lancement `MCP` local passe par `./scripts/cad_stack.sh mcp`, ce qui remplace le vieux helper local non versionné du sous-module.

Le workspace monté dans les conteneurs est, par défaut, la racine du repo. Pour pointer ailleurs:

```bash
CAD_WORKSPACE_DIR=/chemin/vers/projets ./scripts/cad_stack.sh up
```

Variables associees:

- `KICAD_VERSION`: version KiCad utilisee pour calculer le plugin dir par defaut
- `KICAD_PLUGIN_DIR`: override du repertoire plugins KiCad
- `CAD_WORKSPACE_DIR`: workspace monte dans `cad_stack`
- `CAD_INSTALL_BUNDLES`: `all`, `fabrication-toolkit` ou `kic-ai`

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
