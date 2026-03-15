# Multi-Repo Open Source Survey — 2026-03-11

## Method

Veille ciblee sur des projets/librairies open source ou officiels, soit similaires au chantier, soit directement reutilisables sans casser le contrat multi-repo.

## Recos a fort levier

| Projet / lib | Source | Pertinence | Fit principal |
| --- | --- | --- | --- |
| LangGraph | https://langchain-ai.github.io/langgraph/ | graphes d'agents stateful, durable execution, HITL | `mascarade` |
| AutoGen | https://microsoft.github.io/autogen/stable/ | patterns multi-agents conversationnels et outillage Python | `mascarade` |
| CrewAI | https://docs.crewai.com/ | abstraction simple `crew / tasks / tools`, utile pour orchestration documentaire | `mascarade` |
| LiteLLM | https://docs.litellm.ai/docs/ | facade multi-provider, fallback, compat OpenAI | `mascarade` |
| OpenHands | https://docs.all-hands.dev/ | benchmark de boucle agentique code-first et comparaison d'autonomie | `mascarade` |
| Langfuse | https://langfuse.com/docs | tracing, evaluation, prompts, observabilite LLM | `mascarade`, `crazy_life` |
| React Flow | https://reactflow.dev/ | editeur de graphes/workflows moderne pour UI | `crazy_life`, `Kill_LIFE` |
| Mermaid | https://mermaid.js.org/ | diagrammes versionnes dans Markdown, zero infra | `mascarade`, `crazy_life`, `Kill_LIFE` |
| Structurizr | https://docs.structurizr.com/ | C4 model as code, cartes d'architecture et dependances | `mascarade`, `crazy_life`, `Kill_LIFE` |
| D2 | https://d2lang.com/ | diagrammes as code plus lisibles qu'un draw.io fige | `mascarade`, `Kill_LIFE` |
| PlatformIO | https://docs.platformio.org/en/latest/ | build/test/dev embarque multi-cibles | `Kill_LIFE` |
| Renode | https://renode.io/ | simulation hardware pour CI embarquee | `Kill_LIFE` |

## Lecture par repo

### `mascarade`

- `LangGraph`:
  bon candidat si l'orchestrateur doit devenir plus declaratif et durable pour les enchainements complexes d'agents.
- `LiteLLM`:
  utile comme couche de normalisation supplementaire si la surface provider continue de grossir.
- `Langfuse`:
  deja tres compatible avec la logique actuelle d'ops/traces; valeur immediate.
- `AutoGen` et `CrewAI`:
  moins structurants que `LangGraph`, mais utiles comme references de design et pour des lanes specialisees.
- `OpenHands`:
  moins a integrer directement qu'a utiliser comme point de comparaison sur les workflows "agent qui code".

### `crazy_life`

- `React Flow`:
  meilleur levier immediat si la lane workflow doit gagner en lisibilite, edition et cartes fonctionnelles.
- `Mermaid`:
  parfait pour versionner les diagrammes de sequence et cartes de fonctionnalite dans la doc sans outillage lourd.
- `Structurizr` ou `D2`:
  a choisir si le cockpit a besoin d'une cartographie d'architecture plus stable que des diagrammes ad hoc.

### `Kill_LIFE`

- `PlatformIO`:
  deja dans l'orbite du repo; continuer a le traiter comme socle standard pour firmware multi-targets.
- `Renode`:
  tres interessant si l'objectif est de monter le niveau de test automation embarque sans toujours avoir le hardware.
- `Mermaid` / `D2` / `Structurizr`:
  utiles pour rendre enfin lisibles les sequences `spec -> workflow -> evidence`.
- `React Flow`:
  pertinent cote `crazy_life` pour l'edition, moins cote `Kill_LIFE` lui-meme qui doit rester source de verite runtime.

## Recommandations concretes

### A adopter rapidement

- `Mermaid` pour tous les diagrammes de sequence et cartes fonctionnelles versionnees.
- `Langfuse` comme surface commune de traces/eval si les lanes LLM continuent de s'etendre.
- `React Flow` comme standard UI pour la visualisation/edition de workflows.

### A prototyper

- `LangGraph` pour une orchestration plus lisible des lanes agents complexes.
- `Renode` pour un lot d'essai sur `Kill_LIFE` afin de mesurer le gain CI sur firmware/hardware.
- `Structurizr` ou `D2` pour industrialiser la cartographie repo/architecture si Mermaid devient trop compact.

### A garder comme references

- `AutoGen`, `CrewAI`, `OpenHands` comme comparatifs de patterns, de contrats outillage et d'experience operateur.

## Why this matters

Le chantier a deja beaucoup d'outillage. Le risque n'est plus le manque de briques, mais la dispersion.
Cette veille ne recommande pas "plus d'agentique" par defaut:

- elle recommande `Mermaid` et `React Flow` pour la clarte documentaire et produit;
- `Langfuse` pour la lisibilite runtime;
- `LangGraph` seulement si le besoin de graphes durables depasse vraiment l'orchestrateur actuel.
