# Plan Mascarade x Kill_LIFE Workflow Editor

## Résumé

Objectif: intégrer dans `mascarade` une lane `Kill_LIFE` avec un **full editor graphique réel** pour les workflows embarqués, en gardant `Kill_LIFE` comme source métier et runtime.

Principes retenus:

- `mascarade/web` héberge le cockpit et l’éditeur graphique
- `mascarade/api` expose une façade sécurisée `/api/killlife/*`
- `Kill_LIFE/workflows/*.json` devient le format canonique éditable
- la v1 supporte `local` et `github`
- la v1 est un éditeur graphique direct, pas une vue formulaire

## TODO Produit et architecture

- [x] Définir un format JSON canonique pour les workflows `Kill_LIFE`
- [x] Créer des workflows seed pour lancer la lane
- [x] Exposer listing, lecture, save, validation et run via `/api/killlife/*`
- [x] Ajouter une lane `Kill_LIFE` dans la navigation `mascarade`
- [x] Ajouter une page registry et une page editor
- [x] Implémenter un canvas graphique éditable avec nœuds et liaisons
- [x] Permettre save, validate, run local et dispatch GitHub depuis l’UI
- [ ] Ajouter Blockly dans les nœuds de logique avancée en lot 2
- [ ] Ajouter import assisté depuis `docs/workflows/*.md`
- [ ] Ajouter diff visuel avant save et historique multi-version

## Interfaces et comportements

- `KILL_LIFE_ROOT` pointe vers le repo `Kill_LIFE`
- `GET /api/killlife/workflows` liste les graphes canoniques
- `GET /api/killlife/workflows/:id` retourne workflow + validation + runs
- `PUT /api/killlife/workflows/:id` sauvegarde le JSON canonique
- `POST /api/killlife/workflows/:id/validate` valide le graphe courant
- `POST /api/killlife/workflows/:id/run` accepte `mode=local|github`
- `GET /api/killlife/evidence/:target` expose les evidence packs ciblés

## Tests attendus

- validation du schéma et des références de nœuds
- rejet des IDs/path traversal
- save atomique + backup local
- run local `Kill_LIFE` avec logs et evidence refs
- dispatch GitHub uniquement sur workflow allowlisté
- build web et API sans casser les lanes existantes

## Hypothèses

- le repo `Kill_LIFE` reste le runtime métier
- `mascarade` reste l’unique shell frontend
- la v1 accepte l’édition directe des JSON, pas des `.github/workflows/*.yml`
