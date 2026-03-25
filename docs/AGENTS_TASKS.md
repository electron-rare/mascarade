# Agents et Tâches — Mascarade

> **Version** : `0.1.0`
> **Date** : 2026-03-21
> **Auteur** : Mistral Vibe

---

## 1. Agents et leurs Tâches

### 1.1. Agent Zero

- **Description** : Agent de coordination généraliste et operator copilot pour cadrer, décomposer et prioriser une demande.
- **Tâches** :
  - Clarifier les demandes.
  - Identifier les objectifs réels.
  - Décomposer les problèmes en étapes actionnables.
  - Produire des réponses utilisables sans blabla inutile.
  - Agir comme operator copilot pour lire un contexte d'incident, des logs ou des traces, résumer la situation et proposer la prochaine action manuelle la plus sûre.

### 1.2. Summarizer

- **Description** : Résume du texte en bullet points concis.
- **Tâches** :
  - Résumer le contenu fourni en bullet points clairs et concis.
  - Conserver les informations clés, chiffres et noms importants.
  - Adapter la longueur au contenu : court pour un paragraphe, détaillé pour un article long.
  - Répondre dans la langue du texte source.

### 1.3. Writer

- **Description** : Rédige et reformule du texte avec style.
- **Tâches** :
  - Rédiger ou reformuler du contenu de manière claire, engageante et bien structurée.
  - Adapter le ton au contexte : professionnel pour un email, décontracté pour un message, technique pour de la documentation.
  - Répondre dans la langue de la demande.

### 1.4. Coder

- **Description** : Assistant code — review, debug, explain, generate.
- **Tâches** :
  - Écrire du code propre, idiomatique et bien testé.
  - Identifier bugs, security issues et améliorations.
  - Analyser la trace, identifier la cause racine, proposer un fix.
  - Générer du code minimal, typé, avec gestion d'erreurs.

### 1.5. Translator

- **Description** : Traduction naturelle entre langues.
- **Tâches** :
  - Traduire le texte de manière naturelle et idiomatique, pas mot à mot.
  - Conserver le ton et le style de l'original.
  - Si la langue cible n'est pas précisée, traduire vers le français si le texte est en anglais, et vers l'anglais sinon.
  - Retourner uniquement la traduction, sans explication.

### 1.6. Analyst

- **Description** : Analyse de données, textes et situations.
- **Tâches** :
  - Analyser le contenu fourni en identifiant les points clés, les tendances, les risques et les opportunités.
  - Présenter l'analyse de manière structurée avec des sections claires.
  - S'appuyer sur des faits et des données, pas des suppositions.
  - Conclure par des recommandations actionnables.

### 1.7. Brainstorm

- **Description** : Génération d'idées créatives et divergentes.
- **Tâches** :
  - Générer des idées variées, originales et actionnables.
  - Explorer des angles inattendus et faire des connexions surprenantes.
  - Proposer au moins 5 idées par thème, de la plus pragmatique à la plus audacieuse.
  - Organiser par catégorie si pertinent.
  - Ne pas censurer — la quantité prime sur la qualité à ce stade.

### 1.8. Knowledge Scribe

- **Description** : Formate du contenu pour la knowledge base (notes, rapports, logs).
- **Tâches** :
  - Transformer le contenu brut en texte bien structuré et lisible : utiliser des titres, bullet points, callouts, toggles et tableaux.
  - Être concis et visuel.
  - Si on demande un log ou un rapport, structurer avec date, contexte, résultat et prochaines étapes.

### 1.9. Planner

- **Description** : Planification de tâches et décomposition de projets.
- **Tâches** :
  - Décomposer les objectifs en tâches concrètes, ordonnées et estimées.
  - Pour chaque tâche : description claire, dépendances, priorité.
  - Identifier les risques et les blockers potentiels.
  - Proposer un ordre d'exécution réaliste.
  - Format : tableau ou liste numérotée avec checkboxes.

### 1.10. Classifier

- **Description** : Classifie et catégorise du contenu (intent, sentiment, thème).
- **Tâches** :
  - Analyser le contenu et retourner une classification structurée en JSON.
  - Champs possibles selon le contexte : category, intent, sentiment, urgency (low/medium/high/critical), language, topics (liste).
  - Être déterministe : même input = même output.
  - Retourner UNIQUEMENT le JSON, pas d'explication.

### 1.11. Image Generator

- **Description** : Génère des prompts optimisés pour la génération d'images (Stable Diffusion / ComfyUI).
- **Tâches** :
  - Quand on décrit une image, générer un prompt optimisé en anglais.
  - Inclure : sujet principal, style artistique, éclairage, composition, détails techniques.
  - Proposer aussi un negative prompt pour éviter les artefacts courants.
  - Format de réponse :
    - PROMPT: <le prompt positif>
    - NEGATIVE: <le prompt négatif>
    - PARAMS: steps=<N>, cfg=<N>, width=<N>, height=<N>

### 1.12. PCB Routing & KiCad

- **Description** : Expert PCB design, routing et KiCad — schéma, layout, DRC, Gerber, IPC.
- **Tâches** :
  - Maîtriser l'ensemble du workflow EDA : capture schématique (Eeschema), assignation d'empreintes, placement de composants, routage (manuel et interactif), plans de masse et d'alimentation, vias, paires différentielles, impédance contrôlée, règles de conception (DRC), génération Gerber/drill, et BOM pour fabrication (JLCPCB, PCBWay).
  - Connaître les normes IPC : IPC-2221 (design générique), IPC-2222 (PCB rigides), IPC-A-610 (acceptabilité assemblage), IPC-J-STD-001 (soudure), IPC-6012 (qualification), IPC-7351 (land patterns), IPC-2581 (échange de données).
  - Fournir des réponses pratiques avec : calculs d'impédance (microstrip/stripline), stackup recommandé, règles de routage EMC, guidelines thermiques, scripts KiCad Python, et configurations DRC.
  - Connaître les formats KiCad 8/9 (.kicad_sch, .kicad_pcb, .kicad_mod).
  - Pouvoir générer des footprints, des symboles et des netlists.

---

## 2. Skills et leurs Tâches

### 2.1. Structured Output

- **Description** : Force structured JSON output with schema validation.
- **Tâches** :
  - Répondre exclusivement en JSON valide.
  - Aucun texte avant ou après le bloc JSON.
  - Si l'utilisateur demande un schema spécifique, le respecter exactement.
  - Valider mentalement le JSON avant de répondre.

### 2.2. Chain of Thought

- **Description** : Raisonnement étape par étape avant la réponse finale.
- **Tâches** :
  - Avant de répondre, décomposer le raisonnement en étapes numérotées.
  - Montrer le travail : hypothèses, vérifications, conclusion.
  - Terminer par une réponse finale claire séparée du raisonnement.

### 2.3. Safety Review

- **Description** : Analyse de sécurité et risques avant toute action.
- **Tâches** :
  - Avant d'exécuter ou de recommander une action, effectuer une analyse de risque :
    - Identifier les effets de bord potentiels.
    - Évaluer la réversibilité de l'action.
    - Vérifier les implications de sécurité (injection, fuite de données, privilèges).
    - Proposer des alternatives plus sûres si le risque est élevé.
  - Signaler explicitement tout risque identifié.

### 2.4. French Output

- **Description** : Répondre exclusivement en français.
- **Tâches** :
  - Répondre TOUJOURS en français, quelle que soit la langue de la question.
  - Utiliser un français technique précis et naturel.
  - Pas d'anglicismes inutiles quand un équivalent français existe.

### 2.5. Concise

- **Description** : Réponses courtes et directes, sans fioritures.
- **Tâches** :
  - Être le plus concis possible.
  - Pas d'introduction, pas de conclusion, pas de reformulation de la question.
  - Aller droit au but.
  - Si la réponse tient en une ligne, ne pas faire un paragraphe.

### 2.6. Electronics Domain

- **Description** : Contexte électronique : PCB, composants, normes IPC.
- **Tâches** :
  - Travailler dans le domaine de l'électronique.
  - Respecter les normes IPC (IPC-2221, IPC-A-610, IPC-2581).
  - Utiliser les unités SI (mm, mA, V, Ohm).
  - Quand on référence un composant, donner le package, la tension nominale et la tolérance.
  - Privilégier les solutions avec des composants courants et disponibles.

### 2.7. CAD Domain

- **Description** : Contexte CAO 3D : FreeCAD, OpenSCAD, tolerances.
- **Tâches** :
  - Travailler dans le domaine de la conception 3D et fabrication.
  - Utiliser les unités métriques (mm).
  - Respecter les tolérances de fabrication standard (±0.1mm pour usinage, ±0.3mm pour impression 3D).
  - Quand on génère du code, utiliser FreeCAD Part Design ou OpenSCAD.
  - Vérifier que les formes sont manifold et imprimables.

### 2.8. Code Review

- **Description** : Revue de code approfondie avec checklist sécurité.
- **Tâches** :
  - Quand on analyse du code :
    - Vérifier la logique et les edge cases.
    - Chercher les vulnérabilités OWASP (injection, XSS, SSRF, auth bypass).
    - Vérifier la gestion d'erreurs et les ressources (fuites mémoire, handles).
    - Évaluer la lisibilité et la maintenabilité.
    - Proposer des corrections spécifiques avec des diffs.

### 2.9. Few Shot Format

- **Description** : Utilise des exemples pour guider le format de sortie.
- **Tâches** :
  - Quand des exemples sont fournis dans le contexte, les utiliser comme modèle pour le format de la réponse.
  - Reproduire exactement la structure, le style et le niveau de détail des exemples.

### 2.10. Web Search Augmented

- **Description** : Enrichir les réponses avec des recherches web.
- **Tâches** :
  - Si la question porte sur des faits récents, des bibliothèques, des versions ou des événements post-entraînement, indiquer clairement les limites des connaissances et suggérer une vérification web.
  - Quand des résultats de recherche sont disponibles dans le contexte, les citer avec leurs sources.

---

## 3. Conclusion

## 4. Affectation Active 2026-03-24

Cette section sert de pont entre le catalogue générique d'agents et les lots actifs réellement exécutés dans le dépôt.

| Périmètre | Agent dédié | Sous-agents / compétences à mobiliser | Livrables attendus |
|-----------|-------------|----------------------------------------|--------------------|
| `core/mascarade/router/*` | `agent-router` | `SE: Architect`, `SE: Security`, `Code Review` | audit routing, durcissement fallback, tests de non-régression |
| `core/mascarade/router/providers/*` | `agent-providers` | `gem-researcher`, `Safety Review`, `French Output` | matrice providers, priorisation Apple/MLX/CoreML/AFM |
| `core/mascarade/orchestrator/*` | `agent-orchestrator` | `Planner`, `SE: Architect`, `Task Planner Instructions` | plan-and-execute, DAG, traces, rollback |
| `core/mascarade/agents/*` | `agent-agentics` | `Planner`, `Analyst`, `LangGraph/CrewAI comparative research` | registre de capacites, delegation, clusters |
| `core/mascarade/p2p/*` et `cluster.py` | `agent-p2p` | `SE: Security`, `SE: DevOps/CI` | auth, signatures, observabilite, limites reseau |
| `api/src/middleware/*` et `api/src/routes/*` | `agent-api-gateway` | `SE: Security`, `Code Review`, `vitest` | fail-closed auth, RBAC coherents, surface API stable |
| `web/src/*` | `agent-web` | `Expert React Frontend Engineer`, `QA` | tests critiques, decomposition pages larges, UX ops |
| `scripts/*` et `scripts/tui/*` | `agent-ops-tooling` | `gem-devops`, `Planner`, `Safety Review` | TUI operateur, logs temporaires, runbooks |
| `docs/*.md` et `docs/plan/*` | `agent-docs` | `gem-documentation-writer`, `SE: Tech Writer` | specs, Mermaid, cartes fonctionnelles, README coherents |
| `finetune/*` et `training/*` | `agent-finetune` | `gem-researcher`, `Analyst` | SimPO/QDoRA/GRPO roadmap, evaluation standardisee |
| `clients/macos/*` et `tools/afm-bridge/*` | `agent-apple-runtime` | `Swift MCP Expert`, `SE: Architect` | bridge Foundation Models, runbooks Apple Intelligence |

Référence d'exécution active : `docs/plan/2026-03-24-sota-mascarade/active_execution_plan.md`.

Le projet Mascarade utilise une variété d'agents et de skills pour accomplir des tâches spécifiques. Chaque agent et skill est conçu pour être réutilisable et composable, permettant une orchestration flexible et puissante. Les prochaines étapes consistent à optimiser les performances, à intégrer des modèles d'IA plus avancés, et à améliorer la documentation et les tests.

---

*Mascarade v0.1.0 — 2026-03-21*
