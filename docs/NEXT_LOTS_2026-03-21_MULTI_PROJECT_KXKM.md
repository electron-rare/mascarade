# Next Lots — 2026-03-21

Plan opérationnel de continuité après intégration `kxkm` dans `mascarade`, en traitant le repo comme partagé.

## Contexte vérifié

- Le core Python porte maintenant:
  - un provider `mistral-agents` branché au routeur actif
  - un bridge `agents.mistral_agents` recâblé sur les IDs/config Mistral actifs
  - un fallback beta conversations -> deprecated completions pour les agents distants Mistral
  - le bridge MCP `kxkm_rag_search`
  - le provider knowledge base `kxkm`
  - le pull DPO `kxkm`
  - les heuristiques RouteLLM demandées
  - la propagation minimale `project_id / federation_scope / knowledge_scope`
  - un namespace de cache `Router.send()/stream()` scoppé projet/connaissance pour éviter les hits inter-projets
  - un import optionnel de `VLLMScheduler` qui ne casse plus le core quand `vllm` n’est pas installé
- La façade API TypeScript porte maintenant:
  - `/api/v2/llm-providers`
  - la propagation du scope projet sur `/api/knowledge-base/search`
  - `/api/cluster/state`
  - `/api/cluster/events`
- Les scripts TUI/control-plane existants sont maintenant cohérents avec les endpoints disponibles.

## Vérifications déjà passées

### Core

```bash
cd /Users/electron/Documents/Projets/mascarade/core && ./.venv/bin/python -m pytest \
  tests/test_mistral_agents.py \
  tests/test_mistral_agents_provider.py \
  tests/test_scheduler_optional_vllm.py \
  tests/test_scheduler.py \
  tests/test_routers_health.py \
  tests/test_routers_agents.py \
  tests/test_routers_chat.py \
  tests/test_router.py \
  tests/test_mcp_client.py \
  tests/test_knowledge_base.py \
  tests/test_finetune.py \
  tests/test_server_knowledge_base_mcp.py \
  -q
```

### API

```bash
cd /Users/electron/Documents/Projets/mascarade/api && npm test -- \
  src/routes/cluster.test.ts \
  src/routes/knowledgeBase.test.ts \
  src/routes/llmProviders.test.ts \
  src/routes/agents.test.ts
```

### Scripts

```bash
bash -n scripts/deploy_control_plane.sh scripts/log_manager.sh scripts/monitor.sh scripts/lib/control_plane_cli.sh
bash scripts/deploy_control_plane.sh --help
bash scripts/log_manager.sh --help
bash scripts/monitor.sh --help
```

## Agents et responsabilités

### Lot A — Core multi-projet / `kxkm`
- Scope: `core/mascarade`, `core/tests`
- État: livré et vérifié sur le sous-ensemble `router + mistral agents + knowledge base + finetune + chat/agents/health + scheduler import`
- Résultat attendu:
  - provider `mistral-agents` réellement branché dans le routeur actif
  - bridge d’agents distants Mistral recâblé sur `settings`
  - recherche RAG `kxkm`
  - DPO `kxkm`
  - RouteLLM cheap/strong local
  - scope projet minimal propagé
  - cache namespace par projet
  - import facultatif `vllm` non bloquant

### Lot B — Façade API / ops
- Scope: `api/src/client`, `api/src/routes`
- État: livré et vérifié
- Résultat attendu:
  - `llm-providers`
  - `cluster/state`
  - `cluster/events`
  - proxy knowledge-base scoppé projet

### Lot C — Scripts TUI / exploitation
- Scope: `scripts/`, `deploy/control-plane/`
- État: renforcé localement
- Résultat attendu:
  - aides CLI cohérentes
  - protection contre le déploiement d’env placeholders
  - meilleure sélection des logs
  - résumé de logs streamé
  - pont `journalctl` minimal pour les unités `systemd`

### Lot D — Docs / recherche
- Scope: `docs/`
- État: en cours
- Résultat attendu:
  - journal de recherche officiel
  - runbook control-plane/TUI
  - lot suivant priorisé

### Lot E — Audit des chantiers concurrents
- Scope: lecture seule
- État: audit reçu
- Résultat attendu:
  - `vllm` traité comme prototype non fusionné
  - `docker-compose` segmentation réseau traité comme chantier parallèle à relire avant merge

## Prochains lots prioritaires

### P0 — Finir le lot Mistral réellement exploitable
- [x] porter `T-MA-038` dans le repo actif `mascarade`
- [x] documenter le mapping `.env` des IDs `mistral_agent_*` sans recopier les secrets dans le repo
- [x] verrouiller la séparation cockpit direct Mistral / runtime `mistral-agents`
- [x] brancher `T-MS-023` Codestral FIM sur le routeur actif, pas sur la copie historique `mascarade-main`
- [ ] garder `T-MA-016/017/021` explicitement bloqués tant que la VM datasets/fine-tune n’est pas disponible

### P0 — Consolider le contrat multi-projet réel
- [~] rendre `project_id` obligatoire sur les enveloppes de requête exposées aux agents
  - `chat`, `agents/run`, `agents/send`, `knowledge-scribe/run-and-push`, `knowledge-base/search`, `memory` sont maintenant rejetés sans `project_id`
  - les appels internes restants hors périmètre immédiat doivent encore être relus (`a2a`, surfaces non routées, certains jobs out-of-band)
- [~] scoper explicitement mémoire, cache et RAG par projet
  - cache `Router.send()/stream()` maintenant scoppé
  - mémoire conversationnelle Redis et persistance mémoire sont maintenant scoppées
  - orchestrator local et worker AI propagent désormais `project_id / knowledge_scope / federation_scope`
  - P2P/discovery et certains stores annexes restent à relire
- [ ] interdire par défaut toute fédération cross-project sans liste explicite
- [ ] vérifier les routes UI/API qui consomment encore un état non scoppé

### P0 — Stabiliser les scripts d’exploitation
- [x] aligner `monitor.sh` et `log_manager.sh` sur des endpoints réels
- [x] empêcher le déploiement accidentel des `.env.example` placeholders
- [x] documenter et exposer la source primaire `journald` pour les unités `systemd`
- [ ] ajouter un smoke local du couple `cluster/state` + `cluster/events` contre une instance live
- [ ] documenter les prérequis distants `node/systemd/rsync/sudo -n`

### P1 — Clarifier les chantiers concurrents
- [ ] décider si `docker-compose.yml` segmenté réseau devient la nouvelle base
- [ ] décider si le lot `vllm` reste en prototype ou passe en intégration contrôlée
- [ ] ne pas fusionner `vllm` tant que la mémoire paged attention locale n’est pas corrigée

### P1 — Documentation de pilotage
- [ ] publier un état de l’architecture cible multi-projet + `kxkm`
- [ ] publier le runbook control-plane/TUI
- [ ] relier ces docs au README si et seulement si le chantier concurrent README est stabilisé

## Risques ouverts

- `api npm run build` reste rouge sur le `node-engine` React/TSX et des dépendances manquantes; ce n’est pas causé par le lot `kxkm`, mais le package n’est pas globalement propre.
- `docker-compose.yml` a un chantier concurrent de segmentation réseau en cours.
- Les artefacts `vllm` présents dans le repo ne sont pas au niveau de qualité requis pour une intégration immédiate.
- le scoping multi-projet reste incomplet sur certaines surfaces annexes (`a2a`, discovery, stores fichiers, quelques chemins UI/API historiques).

## Décisions prises

- Ne pas réécrire les docs existantes déjà actives; créer des docs nouvelles pour la continuité.
- Ne pas intégrer `vllm` tant que son contrat mémoire/scheduler n’est pas corrigé.
- Préférer une façade API minimale cohérente avec les scripts plutôt qu’un backend parallèle.
- traiter `anthropic:` comme alias d’entrée vers le provider `claude` sur l’API chat, sans changer le contrat interne des providers.
