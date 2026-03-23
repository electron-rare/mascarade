# Code Audit Report — Mascarade — 2026-03-16

## Résumé exécutif

Audit statique du code source des trois composants principaux (`core/`, `api/`, `web/`) portant sur la qualité, la maintenabilité, la sécurité et les anti-patterns. L'analyse couvre les fichiers Python, TypeScript et React du dépôt.

Constat global:
- Plusieurs fichiers dépassent largement les 1000 lignes, rendant la maintenance et les revues difficiles.
- Des imports dupliqués et inutilisés persistent dans les fichiers critiques (`server.py`, `cluster.py`).
- La sécurité applicative est globalement correcte (pas de secrets en dur, subprocess sûrs), mais le chargement dynamique de modules mérite une vigilance continue.
- Les composants React frontaux souffrent d'une complexité d'état excessive sans découpage.
- Aucun `except:` nu n'a été détecté — la gestion d'erreurs est généralement structurée.

Niveau de risque code: **Moyen-Haut** pour la maintenabilité, **Moyen** pour la sécurité interne.

## Portée et méthode

- Analyse statique: imports, taille de fichiers, patterns dangereux, anti-patterns.
- Périmètre: `core/mascarade/`, `api/src/`, `web/src/`.
- Outils: grep, wc, inspection manuelle des fichiers critiques.

## Points positifs

1. Aucun secret en dur détecté dans le code suivi.
2. Les appels `subprocess.run()` utilisent des listes d'arguments (pas de `shell=True`).
3. La validation FreeCAD/MCP bloque `eval()`, `exec()`, `__import__()` via parsing AST (`core/mascarade/mcp/client.py:177-214`).
4. Aucun `except:` nu — toutes les clauses catch sont typées.
5. Les requêtes base de données sont paramétrées (pas d'injection SQL).

---

## Findings priorisés

### F-001 — `server.py` est un fichier monolithique de 2822 lignes
- Sévérité: **Critique**
- Catégorie: Anti-pattern / Fichier surdimensionné
- Fichier: `core/mascarade/server.py`
- Impact: revues de code quasi impossibles, risque élevé de régressions, temps de navigation excessif.
- Détails:
  - Le fichier concentre routes FastAPI, modèles Pydantic, logique métier et configuration.
  - Imports dupliqués aux lignes 10/13 (`asynccontextmanager`), 18/20 (`Response, StreamingResponse`), 19/21 (`BaseModel, Field`).
  - Import inutilisé: `ConfigDict` de pydantic (ligne 19).
- Correction suggérée: extraire les routes par domaine (`routes/chat.py`, `routes/agents.py`, `routes/ops.py`, etc.), isoler les modèles Pydantic dans `models/`.

### F-002 — `mcp/client.py` concentre 1451 lignes de logique hétérogène
- Sévérité: **Haute**
- Catégorie: Anti-pattern / Fichier surdimensionné
- Fichier: `core/mascarade/mcp/client.py`
- Impact: couplage fort entre protocole MCP, validation sécurité FreeCAD, knowledge-base et OpenSCAD.
- Détails:
  - Classe `McpRuntimeClient` avec des méthodes couvrant 4 domaines distincts.
  - Constantes globales de sécurité FreeCAD (lignes 28-70) mélangées avec la logique client.
- Correction suggérée: extraire `freecad_validator.py`, `knowledge_base_client.py` et `openscad_client.py`.

### F-003 — `cluster.py` atteint 1112 lignes avec import dupliqué
- Sévérité: **Haute**
- Catégorie: Dead code / Fichier surdimensionné
- Fichier: `core/mascarade/cluster.py`
- Impact: maintenabilité réduite, confusion sur les dépendances.
- Détails:
  - Import dupliqué de `socket` (lignes 11 et 15).
  - Mélange authentification cluster, découverte mDNS, gestion des peers et health checks.
- Correction suggérée: supprimer l'import dupliqué, extraire `cluster/discovery.py`, `cluster/auth.py`, `cluster/health.py`.

### F-004 — `router/router.py` utilise `__import__()` dynamique
- Sévérité: **Haute**
- Catégorie: Sécurité
- Fichier: `core/mascarade/router/router.py:126`
- Impact: si le nom de module provient d'une entrée non validée, risque d'injection de module.
- Détails:
  - `module = __import__(module_name, fromlist=[class_name])` pour charger les providers.
  - Le même pattern existe dans `core/mascarade/provider_admin.py:491`.
  - En l'état, les noms sont issus du registre interne — risque atténué mais non éliminé.
- Correction suggérée: utiliser `importlib.import_module()` avec une allowlist explicite de modules autorisés.

### F-005 — `api/src/routes/ops.ts` atteint 1925 lignes
- Sévérité: **Haute**
- Catégorie: Anti-pattern / Fichier surdimensionné
- Fichier: `api/src/routes/ops.ts`
- Impact: fichier de routes le plus volumineux du projet, difficile à maintenir et tester.
- Correction suggérée: découper par sous-domaine ops (`ops/logs.ts`, `ops/monitor.ts`, `ops/agents.ts`).

### F-006 — `api/src/client/core.ts` contient 1089 lignes de client HTTP
- Sévérité: **Moyenne**
- Catégorie: Fichier surdimensionné
- Fichier: `api/src/client/core.ts`
- Impact: client monolithique couplant tous les appels vers le core Python.
- Correction suggérée: découper par domaine fonctionnel.

### F-007 — Composants React frontaux surdimensionnés avec état complexe
- Sévérité: **Haute**
- Catégorie: Anti-pattern
- Fichiers:
  - `web/src/pages/Logs.tsx` — 1468 lignes, 13+ hooks `useState`
  - `web/src/pages/Settings.tsx` — 1129 lignes, état dupliqué entre sections
  - `web/src/pages/OpsHub.tsx` — 1092 lignes
  - `web/src/pages/Orchestrate.tsx` — 1028 lignes
  - `web/src/pages/KillLifeWorkflowEditor.tsx` — 1019 lignes
- Impact: prop drilling, re-renders excessifs, difficulté de test unitaire.
- Détails:
  - `Logs.tsx` lignes 243-289: 13 appels `useState` séparés dans un seul composant.
  - `Settings.tsx`: patterns d'état dupliqués entre sections provider et secrets.
- Correction suggérée: extraire des sous-composants, utiliser `useReducer` ou un state manager (Zustand) pour l'état lié.

### F-008 — Imports dupliqués dans `server.py`
- Sévérité: **Moyenne**
- Catégorie: Dead code
- Fichier: `core/mascarade/server.py:10-21`
- Impact: confusion lors de la lecture, risque de divergence si un import est modifié sans l'autre.
- Détails:
  - Ligne 10 et 13: `from contextlib import asynccontextmanager` (dupliqué)
  - Ligne 18 et 20: `from fastapi.responses import Response, StreamingResponse` (dupliqué)
  - Ligne 19 et 21: `from pydantic import BaseModel, Field` (dupliqué)
  - Ligne 19: `ConfigDict` importé mais jamais utilisé
- Correction suggérée: supprimer les doublons, exécuter `ruff check --fix`.

### F-009 — `orchestrator/engine.py` est une god class de 921 lignes
- Sévérité: **Moyenne**
- Catégorie: Anti-pattern
- Fichier: `core/mascarade/orchestrator/engine.py:111-921`
- Impact: classe `Orchestrator` avec 17+ méthodes mélangeant exécution séquentielle, parallèle, pipeline et gestion d'agents.
- Correction suggérée: extraire les stratégies d'exécution dans des classes séparées (pattern Strategy).

### F-010 — `auth.py` et `device_voice.py` approchent les 650 lignes
- Sévérité: **Moyenne**
- Catégorie: Fichier surdimensionné
- Fichiers:
  - `core/mascarade/auth.py` — 635 lignes
  - `core/mascarade/device_voice.py` — 663 lignes
- Impact: maintenabilité modérément dégradée.
- Correction suggérée: surveiller la croissance, envisager un découpage si les fichiers continuent de grossir.

### F-011 — `provider_admin.py` utilise `__import__()` dynamique
- Sévérité: **Moyenne**
- Catégorie: Sécurité
- Fichier: `core/mascarade/provider_admin.py:491`
- Impact: même risque que F-004, surface d'attaque additionnelle.
- Correction suggérée: centraliser le chargement dynamique dans un utilitaire unique avec allowlist.

### F-012 — `api/src/lib/killlife.ts` atteint 924 lignes
- Sévérité: **Basse**
- Catégorie: Fichier surdimensionné
- Fichier: `api/src/lib/killlife.ts`
- Impact: couplage avec le projet Kill_LIFE, difficulté de maintenance isolée.
- Correction suggérée: découper par fonctionnalité si le fichier continue de croître.

### F-013 — Manque de docstrings sur les méthodes complexes de l'orchestrateur
- Sévérité: **Basse**
- Catégorie: Qualité de code
- Fichier: `core/mascarade/orchestrator/engine.py`
- Impact: onboarding et compréhension ralentis pour les contributeurs.
- Correction suggérée: ajouter des docstrings aux méthodes publiques de la classe `Orchestrator`.

---

## Synthèse par catégorie

| Catégorie | Critique | Haute | Moyenne | Basse | Total |
|-----------|----------|-------|---------|-------|-------|
| Fichier surdimensionné | 1 | 3 | 3 | 1 | 8 |
| Anti-pattern | — | 1 | 1 | — | 2 |
| Sécurité | — | 1 | 1 | — | 2 |
| Dead code | — | 1 | 1 | — | 2 |
| Qualité de code | — | — | — | 1 | 1 |
| **Total** | **1** | **6** | **6** | **2** | **15** |

## Actions recommandées par priorité

### Immédiat (Critique)
1. Découper `server.py` en modules de routes et modèles.

### Court terme (Haute)
2. Nettoyer les imports dupliqués/inutilisés (`ruff check --fix`).
3. Découper `mcp/client.py` et `cluster.py` en sous-modules.
4. Sécuriser `__import__()` avec une allowlist centralisée.
5. Découper `ops.ts` côté API.
6. Refactorer les composants React >1000 lignes.

### Moyen terme (Moyenne)
7. Extraire les stratégies d'exécution de l'orchestrateur.
8. Surveiller la croissance de `auth.py` et `device_voice.py`.

### Backlog (Basse)
9. Ajouter des docstrings aux méthodes complexes.
10. Surveiller `killlife.ts`.
