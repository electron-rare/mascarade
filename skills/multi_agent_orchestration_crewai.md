# Multi-Agent Orchestration (CrewAI)

## Objectif

Orchestrer plusieurs agents spécialisés (planner, researcher, writer, reviewer) pour exécuter une tâche complexe avec validation intermédiaire.

## Pré-requis

- Dépendances Python installées dans `core` :
  - `crewai`
  - `openai-agents`
- Variables d'environnement LLM configurées (`ANTHROPIC_API_KEY` ou `OPENAI_API_KEY`).

## Workflow recommandé

1. Décomposer la demande en tâches atomiques.
2. Assigner chaque tâche à un rôle d'agent explicite.
3. Exécuter avec timeouts courts et retries.
4. Fusionner les sorties puis lancer un agent "reviewer".
5. Retourner la réponse finale + traces minimales d'exécution.

## Rôles d'agents

- `planner`: plan d'exécution et priorisation.
- `researcher`: collecte de contexte/faits.
- `implementer`: production de code/contenu.
- `reviewer`: contrôle qualité et risques.

## Garde-fous

- Pas d'exécution destructive sans confirmation.
- Limiter la profondeur d'outils externes.
- Renvoyer explicitement les blocages (auth, réseau, dépendances).

