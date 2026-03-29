---
description: "Execute les tests pytest et Playwright, audite les echecs, planifie les correctifs via skills et subagents, puis relance jusqu'a green."
name: "Test Audit Fix Loop"
argument-hint: "Scope : rag | conversation | api | frontend | all (defaut: all)"
agent: "agent"
tools: [search, read, execute, editFiles]
---

# Test Audit Fix Loop

Boucle autonome de qualite : lance les tests, audite les echecs, applique des correctifs via skills et subagents, puis relance jusqu'a ce que tout soit vert.

## Scope

Scope demande : `${input:scope:all}`

- `rag` : pytest `tests/test_agentic_rag.py` + Playwright `tests/api/rag.spec.ts`
- `conversation` : pytest `tests/test_router.py` + Playwright `tests/api/conversation.spec.ts`
- `api` : `cd api && npm test` + Playwright `tests/api/**`
- `frontend` : `cd web && npm test -- --run` + Playwright `tests/web/**`
- `all` : toutes les suites ci-dessous

## Phase 1 - Execution des tests

Lance les suites dans cet ordre et capture stdout + stderr.

Python core :

```bash
cd core && python -m pytest tests/test_agentic_rag.py tests/test_router.py tests/test_auth.py -v --tb=short 2>&1
```

API TypeScript :

```bash
cd api && npm test 2>&1
```

Frontend :

```bash
cd web && npm test -- --run 2>&1
```

E2E Playwright :

```bash
cd e2e && npx playwright test tests/api/rag.spec.ts tests/api/conversation.spec.ts tests/api/health.spec.ts tests/api/auth-gates.spec.ts tests/api/validation.spec.ts tests/web/navigation.spec.ts --reporter=list 2>&1
```

## Phase 2 - Audit des resultats

Pour chaque suite, produire un tableau compact : PASS, FAIL, SKIP, erreurs principales.

Pour chaque echec, extraire :

1. nom du test
2. premiere ligne du message d'erreur
3. fichier source probable
4. categorie : `CONFIG`, `MOCK`, `LOGIC`, `ASSERTION`

Si tout est vert, afficher `TOUT VERT` et arreter la boucle.

## Phase 3 - Plan de correction

Utiliser le skill `refactor-plan` pour proposer des correctifs minimaux.

Format attendu :

```text
Correctif #N - <nom du test>
Categorie    : CONFIG | MOCK | LOGIC | ASSERTION
Fichier cible: chemin/vers/fichier
Action       : modification minimale
Risque       : low | medium | high
Rollback     : retour arriere
```

Regles :

- `MOCK` : ajouter la route manquante dans `e2e/mock-api/server.mjs`
- `CONFIG` : verifier `core/pyproject.toml`, `api/package.json`, `web/package.json`
- `LOGIC` : lire le fichier source avant patch
- `ASSERTION` : corriger le test, pas le code source

## Phase 4 - Application des correctifs

Utiliser le subagent `SWE` pour chaque correctif.

Apres chaque patch, relancer uniquement la suite concernee :

- `MOCK` : `cd e2e && npx playwright test <spec_en_echec> --reporter=list`
- `CONFIG` : relancer la suite du stack concerne
- `LOGIC` : `cd core && python -m pytest <test_en_echec> -v`
- `ASSERTION` : relancer le test modifie

Si le test reste rouge, tenter une variante minimale puis escalader si besoin.

## Phase 5 - Reboucler

1. relancer la Phase 1 complete
2. repeter jusqu'a `TOUT VERT`
3. s'arreter apres 3 iterations maximum avec un rapport d'escalade si necessaire

## Regles de securite

- ne jamais supprimer de tests
- ne jamais toucher `.env` ni les secrets
- ne pas modifier `core/conftest.py` sans signaler le risque
- demander confirmation avant patch sur `auth.py`, `rbac.py`, `config.py`