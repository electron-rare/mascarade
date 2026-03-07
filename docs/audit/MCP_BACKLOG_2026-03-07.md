# Backlog MCP — 2026-03-07

## Résumé
Ce backlog isole uniquement la couche MCP observée autour de `mascarade`, `Kill_LIFE` et `crazy_life`.

Docs d’exécution associées:
- `mascarade/docs/audit/MCP_RUNTIME_PLAN_2026-03-07.md`
- `mascarade/docs/audit/MCP_RUNTIME_TODO_2026-03-07.md`
- `Kill_LIFE/docs/plans/15_plan_mcp_stack.md`
- `Kill_LIFE/docs/plans/15_todo_mcp_stack.md`
- `crazy_life/docs/MCP_PLAN_2026-03-07.md`
- `crazy_life/docs/MCP_TODO_2026-03-07.md`

Constat synthétique:
- un seul MCP "bundled" ambitieux existe vraiment: `finetune/kicad_mcp_server`
- un MCP déclaré dans `Kill_LIFE` est cassé (`validate-specs`)
- le MCP schématique `kicad-sch-mcp` est documenté, mais pas installé sur cette machine
- les autres MCP de `kicad_kic_ai` sont surtout des démos, mocks ou serveurs simulés
- il existe une dérive de protocole MCP entre la stack récente (`2025-06-18`) et les micro-serveurs / clients locaux (`2024-11-05`)

## Inventaire actuel

| Surface MCP | Emplacement | État observé | Statut |
| --- | --- | --- | --- |
| `validate-specs` | `Kill_LIFE/mcp.json` | pointe vers `tools/validate_specs.py` absent | Cassé |
| `kicad-sch-mcp` | `Kill_LIFE/docs/MCP_SETUP.md` | recommandé en doc, non installé sur la machine | Non déployé |
| `kicad_mcp_server` | `mascarade/finetune/kicad_mcp_server` | build présent, transport `stdio`, crash runtime sur permissions + libs KiCad non chargées | Partiel |
| `component_database` | `mascarade/finetune/kicad_kic_ai/mcp_servers/component_db.py` | base en mémoire d’exemple | Mock |
| `nexar_api` | `mascarade/finetune/kicad_kic_ai/mcp_servers/nexar.py` | mode démo par défaut, incohérence `api_token` / `api_key` | Fragile |
| `kicad_tools` | `mascarade/finetune/kicad_kic_ai/mcp_servers/kicad_tools.py` | réponses simulées, pas de backend KiCad réel | Mock |

## J0 — Remédiations critiques

### MCP-001 — Corriger ou retirer le serveur `validate-specs`
- Priorité: **Critique**
- Problème: `Kill_LIFE/mcp.json` déclare un serveur local non lançable.
- Action:
  - soit implémenter `tools/validate_specs.py`,
  - soit retirer l’entrée `validate-specs` du fichier de config versionné.
- Critères d’acceptation:
  1. `Kill_LIFE/mcp.json` ne référence plus aucun chemin absent.
  2. le serveur déclaré répond au minimum à `initialize` et `tools/list`.

### MCP-002 — Choisir un seul chemin KiCad MCP supporté
- Priorité: **Critique**
- Problème: la doc de `Kill_LIFE` pousse `kicad-sch-mcp`, tandis que le repo embarque aussi `finetune/kicad_mcp_server`.
- Action:
  - décider si le serveur supporté est `kicad-sch-mcp`, `kicad_mcp_server`, ou les deux avec rôles distincts;
  - aligner `docs/MCP_SETUP.md`, `deploy/cad/README.md` et les scripts de lancement.
- Critères d’acceptation:
  1. un opérateur sait quel serveur installer/lancer sans ambiguïté.
  2. la doc n’expose plus deux chemins concurrents sans matrice de support.

### MCP-003 — Rendre `kicad_mcp_server` réellement lançable
- Priorité: **Critique**
- Problème: le serveur démarre puis tombe sur `PermissionError: /opt/kicad-mcp/data`.
- Action:
  - rendre le répertoire de données writable dans le conteneur;
  - valider les permissions de `HOME`, cache et data;
  - ajouter un smoke test de démarrage `initialize -> tools/list -> resources/list`.
- Critères d’acceptation:
  1. le serveur ne crash plus au boot.
  2. le smoke test passe sur cette machine.

### MCP-004 — Charger correctement les bibliothèques KiCad côté MCP
- Priorité: **Critique**
- Problème: le log montre `0 footprint libraries` et `0 symbol libraries`.
- Action:
  - corriger le chargement de `sym-lib-table` et `fp-lib-table`;
  - vérifier le mode de fallback SWIG et les chemins Linux effectifs;
  - ajouter un test qui confirme qu’au moins une lib symbole et une lib footprint sont visibles.
- Critères d’acceptation:
  1. le serveur liste des libs réelles.
  2. un outil de découverte de symboles fonctionne sur une install Linux standard.

## J7 — Stabilisation MCP

### MCP-005 — Aligner les versions de protocole MCP
- Priorité: **Haute**
- Problème: `kicad_mcp_server` annonce `2025-06-18`, alors que `kicad_kic_ai` parle `2024-11-05`.
- Action:
  - choisir une version cible;
  - mettre à jour clients/serveurs locaux;
  - documenter la matrice de compatibilité.
- Critères d’acceptation:
  1. plus aucun client local n’utilise une version différente sans justification.
  2. les handshakes `initialize` sont homogènes.

### MCP-006 — Désactiver par défaut les serveurs MCP mockés
- Priorité: **Haute**
- Problème: `component_database` et `kicad_tools` donnent l’apparence d’outils réels alors qu’ils renvoient des données d’exemple/simulées.
- Action:
  - passer ces serveurs en `enabled: false` tant qu’ils restent mockés,
  - ou les marquer explicitement `demo-only` dans la config et l’UI.
- Critères d’acceptation:
  1. aucun MCP mock n’est présenté comme production-ready.
  2. l’utilisateur voit clairement quand il travaille sur des données simulées.

### MCP-007 — Corriger `nexar_api` pour le vrai mode API
- Priorité: **Haute**
- Problème: le serveur mélange `self.api_token` et `self.api_key`, ce qui fragilise le chemin "réel".
- Action:
  - unifier la variable d’authentification;
  - tester le mode token réel;
  - rendre le mode démo explicite dans les réponses.
- Critères d’acceptation:
  1. le mode API réel fonctionne avec `NEXAR_TOKEN`.
  2. le mode démo n’est jamais confondu avec du vrai pricing live.

### MCP-008 — Remplacer `kicad_tools` simulé par un backend réel ou le retirer
- Priorité: **Haute**
- Problème: les analyses et BOM retournent des réponses simulées.
- Action:
  - brancher ce serveur sur un backend KiCad réel,
  - ou retirer ces outils du chemin de production.
- Critères d’acceptation:
  1. les résultats proviennent d’un projet KiCad réel.
  2. aucun payload simulé ne sort en mode production.

### MCP-009 — Ajouter un outillage de test MCP standard
- Priorité: **Haute**
- Problème: il n’existe pas de check simple et versionné pour valider un serveur MCP local.
- Action:
  - ajouter un script de smoke test par serveur supporté;
  - tester `initialize`, `tools/list`, `tools/call` minimal, et si présent `resources/list`.
- Critères d’acceptation:
  1. chaque serveur supporté a un smoke test automatisable.
  2. la CI ou le runbook peut distinguer "installé", "lançable", "fonctionnel".

## J30 — Industrialisation

### MCP-010 — Réconcilier la doc MCP dupliquée
- Priorité: **Moyenne**
- Problème: `Kill_LIFE/docs/MCP_SETUP.md` et `ai-agentic-embedded-base/docs/MCP_SETUP.md` dupliquent les mêmes consignes.
- Action:
  - choisir une source canonique;
  - transformer l’autre en simple pointeur ou copie synchronisée contrôlée.
- Critères d’acceptation:
  1. une seule doc fait foi.
  2. aucun drift de recommandations n’apparaît entre les deux arbres.

### MCP-011 — Clarifier la politique transport/sécurité MCP
- Priorité: **Moyenne**
- Problème: tout est pensé en `stdio`, ce qui est sain localement, mais aucune politique formelle n’est écrite.
- Action:
  - formaliser `stdio only` par défaut;
  - documenter qu’aucun transport réseau MCP n’est supporté sans auth + chiffrement + ACL explicites.
- Critères d’acceptation:
  1. la posture réseau MCP est documentée.
  2. aucun serveur MCP n’expose de port par défaut.

### MCP-012 — Ajouter l’observabilité MCP
- Priorité: **Moyenne**
- Problème: les logs existent, mais il n’y a pas de statut MCP consolidé dans les outils ops.
- Action:
  - exposer un état synthétique "MCP ready / degraded / failed";
  - inclure derniers échecs de handshake, version protocole et nombre d’outils disponibles.
- Critères d’acceptation:
  1. un opérateur peut voir si le serveur MCP est réellement prêt.
  2. les erreurs MCP ne se limitent plus à des logs locaux dispersés.

## Ce qu’il reste à implémenter

### 1. `validate-specs`
- implémenter réellement le serveur local référencé dans `Kill_LIFE/mcp.json`
- ou supprimer définitivement cette promesse de config

### 2. `kicad-sch-mcp`
- installer/packager le binaire sur la machine
- fournir une commande de bootstrap reproductible
- ajouter un smoke test local

### 3. `kicad_mcp_server`
- corriger le boot Linux sans crash permission
- charger correctement `sym-lib-table` et `fp-lib-table`
- stabiliser le backend IPC ou documenter clairement le fallback SWIG
- intégrer complètement le dynamic symbol loading à l’interface MCP
  - `add_schematic_component_dynamic`
  - auto-détection / recherche de symboles
  - gestion multi-unités et previews si ces features restent dans la roadmap

### 4. `kicad_kic_ai` MCP
- remplacer `component_database` en mémoire par une vraie source de composants
- corriger `nexar_api` pour le mode réel
- remplacer `kicad_tools` simulé par des analyses KiCad réelles
- décider si ces trois serveurs doivent survivre comme MCP séparés ou être absorbés par le serveur KiCad principal

### 5. Couche transverse
- unifier la version de protocole MCP sur tout le parc
- unifier la doc et la matrice de support
- fournir un test d’acceptation MCP unique par repo
- décider quelles surfaces MCP sont "prod", "expérimentales" ou "démo"

## Ordre recommandé
1. `MCP-001` à `MCP-004`
2. `MCP-005` à `MCP-009`
3. seulement ensuite implémenter les fonctionnalités MCP restantes

## Décision par défaut recommandée
- garder `stdio` comme seul transport supporté localement
- traiter `finetune/kicad_mcp_server` comme serveur KiCad principal à stabiliser
- considérer `kicad_kic_ai/mcp_servers/*` comme environnement de prototypage tant qu’ils restent mockés/simulés
- supprimer toute config MCP versionnée qui ne pointe pas vers un exécutable réel
