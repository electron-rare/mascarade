# MCP / Agentics Architecture

Last updated: 2026-03-08

Document canonique de frontiere entre `MCP`, orchestration `mascarade`, observabilite et ouverture future de `A2A`.

## Planes

### Tool plane = `MCP`

Les acces outils/systemes passent par des serveurs MCP specialises:

- `kicad`
- `validate-specs`
- `knowledge-base`
- `github-dispatch`
- `freecad`
- `openscad`
- `huggingface` comme surface distante supportee par le cockpit ops

Regles:

- un serveur par domaine
- transport `stdio` local par defaut, sauf surface distante explicitement assumee
- smoke JSON versionne par serveur
- statut synthetique expose dans `/api/ops/summary`

### Execution plane = `mascarade`

`mascarade` porte:

- l'orchestrateur multi-agents
- la gestion des secrets runtime
- les vues operateur `OpsHub`, `Logs`, `Orchestrate`
- l'agregation des probes MCP

Etat courant:

- l'observabilite MCP est branchee et exposee cote ops
- le core emet maintenant des evenements `mcp_call_started`, `mcp_call_completed`, `mcp_call_failed` dans `AgentTraceBuffer`
- la knowledge base et `github-dispatch` utilisent maintenant un client MCP interne commun comme chemin canonique
- `freecad-designer` declare maintenant `freecad_mcp`
- `FreeCAD` et `OpenSCAD` utilisent maintenant ce client comme chemin metier canonique via leurs routes core/API dediees
- les integrations directes restantes ne servent plus de chemin runtime canonique; elles restent seulement pour compat/tests

Conclusion:

- `A-003` est ferme: le runtime canonique passe maintenant par les MCP specialises pour la knowledge base, `GitHub`, `FreeCAD` et `OpenSCAD`

### Observability plane = `OTel` + `ops-agent` + `Loki` + `Grafana`

Le plan d'observabilite couvre:

- probes MCP synthetiques par serveur
- logs structurés
- traces/runtime metrics OTel
- dashboards Grafana
- actions operateur de reprobe depuis l'UI

Etat courant:

- `ops-agent` sait sonder `kicad`, `validate-specs`, `knowledge-base`, `github-dispatch`, `freecad`, `openscad`, `huggingface`
- `OpsHub` et `Logs` peuvent lancer une reprobe par serveur
- `ops-agent` exporte maintenant des evenements OTLP structures `source=mcp-probe` pour tous les probes MCP synthetiques supportes
- le core exporte maintenant des traces metier `mcp_call_*` corrigees par `run_id`
- `/api/ops/logs/query` et la page `Logs` savent filtrer `source=mcp-probe`, `mcp_server`, `mcp_tool`, `mcp_status`
- le dashboard Grafana `Mascarade AI Runtime` expose maintenant des panneaux MCP dedies aux probes, erreurs et volumes d'appels

Conclusion:

- `A-002` est ferme: l'observabilite MCP est maintenant exploitable en synthese, en historique ops, en timeline applicative et dans Grafana

### Operator plane = `crazy_life` et `mascarade/web`

Le cockpit expose:

- le statut agrege MCP
- le detail par serveur
- les probes manuelles
- une supervision par `run_id`

Etat courant:

- `A-201` et `A-202` sont livres
- `A-203` est ferme: la supervision par `run_id` existe, la timeline `Orchestrate` expose `mcp_server`, `mcp_tool`, `mcp_status`, et les validations live `github-dispatch`, `FreeCAD`, `OpenSCAD` sont corrigees par ce meme `run_id`

## A2A

`A2A` reste ferme dans le runtime courant.

Decision courante:

- `A-005` est ferme en decision `deferred / not now`
- la couche MCP specialisee couvre deja le tool plane
- l'orchestrateur `mascarade` couvre le besoin courant sans handoff inter-runtime dedie

Condition de reouverture minimale:

1. au moins deux agents autonomes doivent devoir se deleguer des taches entre runtimes ou domaines de confiance distincts
2. ce besoin ne doit pas etre satisfaisable proprement avec l'orchestrateur actuel + MCP
3. l'observabilite MCP doit rester homogene et stable sous charge reelle

Si `A2A` s'ouvre plus tard:

- il sert uniquement aux handoffs inter-agents
- il ne remplace pas `MCP` pour l'acces aux outils

## Restes specialises ouverts

Les restes techniques encore ouverts ne sont plus sur la ligne `A-*`, mais sur le backlog KiCad specialise:

- `K-014`: bloque sur cette machine car `NEXAR_TOKEN` est absent et `nexar_api` reste en mode demo
- `K-012`: reste une validation host-native optionnelle; le runtime canonique actuel utilise deja le conteneur KiCad MCP avec succes

## Repartition pratique par repo

- `Kill_LIFE`: launchers, smokes, runtimes locaux, specs et matrices canoniques
- `mascarade`: orchestration, ops, secrets runtime, agregation et supervision
- `crazy_life`: cockpit et actions operateur, sans ownership serveur
