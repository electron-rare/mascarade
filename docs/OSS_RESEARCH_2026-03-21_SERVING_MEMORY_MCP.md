# OSS Research — 2026-03-21

Recherche ciblée sur les briques de référence pour `mascarade`:
- serving distribué
- routage
- multitenancy RAG
- mémoire
- protocole MCP

Sources officielles utilisées:
- [Ray Serve architecture](https://docs.ray.io/en/latest/serve/architecture.html)
- [Ray Serve LLM routing policies](https://docs.ray.io/en/latest/serve/llm/architecture/routing-policies.html)
- [vLLM distributed inference and serving](https://docs.vllm.ai/en/v0.10.0/serving/distributed_serving.html)
- [Qdrant multitenancy guide](https://qdrant.tech/documentation/guides/multitenancy/)
- [Mem0 OSS overview](https://docs.mem0.ai/open-source/overview)
- [MCP architecture overview](https://modelcontextprotocol.io/docs/learn/architecture)

## Résumé exécutable

- **MCP** est la bonne abstraction pour exposer outils, ressources et prompts, pas pour porter tout le scheduling distribué.
- **Ray Serve** reste la référence utile pour séparer ingress, routing policy et replicas, même si `mascarade` ne doit pas migrer vers Ray immédiatement.
- **vLLM** reste la référence utile pour l’inférence GPU lourde, surtout pour le continuous batching et le multi-GPU; en multi-nœud, sa doc confirme un backend Ray.
- **Qdrant** reste une bonne base pour le RAG multi-projet, à condition de traiter le projet comme frontière logique stricte.
- **Mem0 OSS** est pertinent comme mémoire self-hosted, mais doit rester scoppé projet et non global.

## Adopt / Adapt / Reject

| Sujet | Décision | Pourquoi |
|---|---|---|
| MCP pour tools/context | Adopt | Aligne `mascarade` avec l’écosystème agentique, sans forcer un redesign total |
| Ray Serve comme modèle d’architecture | Adapt | Bonne référence de séparation ingress/routing/replicas, mais migration complète non justifiée à ce stade |
| vLLM pour serving GPU principal | Adapt | Pertinent pour `KXKM-AI`, mais seulement via intégration contrôlée et tests réels |
| Qdrant multitenancy | Adopt | Convient au RAG par `project_id` avec filtres et isolation logique |
| Mem0 OSS | Adapt | Utile pour mémoire self-hosted, mais pas comme mémoire globale partagée |
| Fédération cross-project implicite | Reject | Incompatible avec le besoin d’isolation interne multi-projet |

## Implications pour Mascarade

### 1. Serving distribué
- Garder l’architecture `gateway -> scheduler -> workers`.
- Réserver `photon-machine` au plan de contrôle.
- Réserver `kxkm` au chemin GPU principal.
- Réserver `tower` au prep/post CPU, embeddings, rerank, OCR, jobs annexes.

### 2. RAG multi-projet
- Chaque chunk indexé doit porter `project_id`.
- La recherche par défaut doit rester `knowledge_scope=project`.
- Le mode `federated` doit exiger une liste explicite `federation_scope`.

### 3. Mémoire
- La mémoire courte durée doit être scoppée session + projet.
- La mémoire persistante doit être scoppée projet.
- Pas de cache de contexte partagé entre projets.

### 4. MCP
- `mascarade` doit consommer des serveurs MCP pour les outils et la connaissance.
- `mascarade` pourra exposer à terme un serveur MCP, mais ce n’est pas le lot critique avant la consolidation multi-projet.

## Recommandations prioritaires

### P0
- imposer `project_id` partout où le contexte traverse les couches
- refuser la fédération implicite
- traiter `Qdrant` et la mémoire comme surfaces multi-tenant strictes

### P1
- documenter une cible `vLLM` réaliste pour `kxkm`, sans prétendre que le prototype actuel est prêt
- clarifier la frontière entre MCP, knowledge bridge et mémoire persistante

### P2
- évaluer un chemin `Mem0 OSS` seulement après verrouillage du contrat multi-projet

## Notes de cohérence

- La doc `vLLM` officielle est utile comme référence de capacités, pas comme justification de l’implémentation locale actuelle.
- La doc MCP officielle confirme que le protocole couvre outils, ressources, prompts et transports, mais pas la politique de placement multi-machine elle-même.

## Revalidation 2026-03-22

Points revalidés sur les sources officielles:

- **Ray Serve** confirme une séparation nette `Controller / Proxy / Replicas`, ce qui reste cohérent avec notre choix `gateway / scheduler / workers` pour `mascarade`.
- **Qdrant** recommande, pour la plupart des cas, une collection par modèle d'embeddings avec partitionnement par payload tenant, et précise que l'option `is_tenant=true` améliore la colocalisation des vecteurs d'un même tenant.
- **Mem0 OSS** se présente comme une mémoire self-hosted avec contrôle complet de l'infrastructure et des données; ses composants par défaut (`Qdrant` local + `SQLite`) renforcent l'idée qu'il faut scoper explicitement par `project_id` au-dessus de la stack.
- **MCP** confirme une architecture `host -> client -> server`, avec une connexion dédiée par client/serveur, et rappelle que le protocole ne décide pas du scheduling applicatif ni du placement distribué.

Conséquence directe pour les vagues en cours:
- le `project_id` doit rester la frontière logique commune entre cache, mémoire, RAG et exécution
- le contrôle-plane `mascarade` doit consommer MCP comme protocole d'outils/contexte, pas comme scheduler multi-machine
