# VS Code Cline + Cody via MCP

## Objectif

Brancher Cline et Cody sur Mascarade sans écrire d'extension VS Code dédiée.

Le point commun retenu est le serveur MCP stdio local de Mascarade :

- launcher Node : `scripts/vscode/mascarade_mcp_stdio.js`
- serveur Python : `core/mascarade/mcp/server.py`

## Ce que fait le launcher

Le launcher :

- résout automatiquement le repo et `core/`
- ajoute `core/` à `PYTHONPATH`
- cherche un interpréteur Python dans cet ordre :
  - `MASCARADE_MCP_PYTHON`
  - `core/.venv/bin/python`
  - `.venv/bin/python`
  - `python3`
  - `python`
- lance `python -m mascarade.mcp.server`

## Vérification rapide

```bash
MASCARADE_MCP_PRINT_ONLY=1 node scripts/vscode/mascarade_mcp_stdio.js
```

Cette commande n'ouvre pas le serveur ; elle affiche juste la résolution effective du runtime.

## Configuration Cline

Créer ou compléter le fichier de settings VS Code ou Cline avec un bloc de ce type :

```json
{
  "cline.mcpServers": {
    "mascarade": {
      "command": "node",
      "args": [
        "/ABS/PATH/TO/mascarade/scripts/vscode/mascarade_mcp_stdio.js"
      ],
      "env": {
        "MASCARADE_PROJECT_ID": "default"
      }
    }
  }
}
```

Exemple prêt à adapter :

- `docs/examples/vscode/cline.settings.mascarade.jsonc`

## Cline via la gateway chat Mascarade

Si l'objectif est que Cline passe par tout le routage LLM de Mascarade, utiliser le provider `OpenAI Compatible` de Cline avec :

- Base URL : `http://localhost:3000/api/v1`
- API Key : `MASCARADE_API_KEY`
- Model ID : le modèle routé par Mascarade

Le endpoint `POST /api/v1/chat/completions` accepte maintenant l'absence de `project_id` et le remplace par `MASCARADE_PROJECT_ID`, ou `default` si la variable n'est pas définie.

Mascarade expose aussi `GET /api/v1/models`, ce qui permet aux clients OpenAI-compatible de récupérer le catalogue de modèles publié par les providers actifs/configurés.

## Configuration Cody

Cody ne se branche pas ici comme provider LLM Mascarade. On le branche comme client Sourcegraph/Cody, et on ajoute Mascarade comme source de contexte outillée via OpenCtx + MCP.

Créer ou compléter `settings.json` avec :

```json
{
  "openctx.providers": {
    "https://openctx.org/npm/@openctx/provider-modelcontextprotocol?mascarade": {
      "nodeCommand": "node",
      "mcp.provider.uri": "file:///ABS/PATH/TO/mascarade/scripts/vscode/mascarade_mcp_stdio.js"
    }
  }
}
```

Exemple prêt à adapter :

- `docs/examples/vscode/cody.settings.mascarade.jsonc`

## Limites utiles

- Cline : l'intégration ci-dessus passe par MCP stdio local.
- Cody : cette intégration ajoute du contexte et des tools via OpenCtx/MCP, mais Cody reste un produit Sourcegraph distinct.
- Au vu des docs Sourcegraph actuelles, Cody demande un environnement Sourcegraph Enterprise / Cody Enterprise pour l'usage standard en 2026.

## Sources officielles

- Cline MCP marketplace : <https://docs.cline.bot/mcp/mcp-marketplace>
- Cline configuration / MCP settings : <https://docs.cline.bot/cline-cli/configuration>
- OpenCtx start : <https://openctx.org/docs/start>
- OpenCtx provider Model Context Protocol : <https://openctx.org/docs/providers/modelcontextprotocol>
- Cody enterprise enablement : <https://sourcegraph.com/docs/cody/explanations/enabling_cody_enterprise>
- Cody FAQ : <https://sourcegraph.com/docs/cody/faq>
