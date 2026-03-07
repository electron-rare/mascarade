# Remediation Backlog — 2026-03-07

## Objectif
Transformer l'audit machine + multi-repo en séquence d'actions exécutable, orientée fiabilité d'exploitation.

## J0 — immédiat

### R-001 — Réduire la pression machine et restaurer de la marge mémoire/swap
- Priorité: **Critique**
- Problème: plusieurs jobs `train_cpu.py` tournent en parallèle alors que la RAM et le swap sont déjà fortement consommés.
- Actions:
  - suspendre ou sérialiser les entraînements CPU non urgents;
  - garder un seul lot de fine-tuning actif tant que la RAM libre reste faible;
  - définir un plafond d'exécution concurrente sur les scripts `finetune/*`.
- Critères d'acceptation:
  1. `free -h` montre un swap sous `1 GiB` utilisé au repos.
  2. `ps --sort=-pmem` ne montre plus 4 à 5 jobs `train_cpu.py` concurrents.

### R-002 — Réactiver une authentification effective sur `mascarade`
- Priorité: **Critique**
- Problème: `MASCARADE_API_KEY` est vide alors que l'hôte expose `80/443`.
- Actions:
  - renseigner un secret fort pour `MASCARADE_API_KEY`;
  - redémarrer `mascarade-api` avec auth active;
  - vérifier qu'un appel sans token sur `/api/ops/summary` ne renvoie plus `200`.
- Critères d'acceptation:
  1. l'environnement runtime n'expose plus `MASCARADE_API_KEY=`.
  2. un appel non authentifié sur `/api/ops/summary` échoue (`401` ou `403`).

### R-003 — Corriger le faux vert des healthchecks / logs critiques
- Priorité: **Critique**
- Problème: `mascarade-core`, `edge-proxy` et `promtail` montrent des erreurs réelles malgré des statuts globalement verts.
- Actions:
  - investiguer les échecs fallback Ollama dans `mascarade-core`;
  - réduire ou corriger les timeouts du flux logs `/api/ops/logs/stream`;
  - traiter les `context deadline exceeded` de `promtail` vers Loki.
- Critères d'acceptation:
  1. `mascarade_docker_logs_key_signals.txt` n'affiche plus ces erreurs après redémarrage à froid.
  2. `/api/ops/summary` ne rapporte plus d'échecs fallback récents.

### R-004 — Rendre les tests Python exécutables localement
- Priorité: **Haute**
- Problème: `pytest` manque dans l'environnement Python système, tandis que `mascarade` dépend d'un `.venv` local et `Kill_LIFE` mélange `pytest` et `unittest`.
- Actions:
  - documenter un environnement Python reproductible par repo;
  - fournir une commande bootstrap unique et une commande de test unique par repo;
  - pour `mascarade`, expliciter et outiller le chemin `.venv/bin/python -m pytest -q` ou équivalent;
  - pour `Kill_LIFE`, unifier `pytest`/`unittest` derrière une entrée standard et documentée.
- Critères d'acceptation:
  1. une commande documentée et stable exécute les tests `mascarade/core` sur une machine fraîche.
  2. une commande documentée et stable exécute la suite Python `Kill_LIFE` sur une machine fraîche.

### R-005 — Geler l'état publiable réel de `crazy_life`
- Priorité: **Haute**
- Problème: le repo se dit canonique mais des parties essentielles sont non suivies par Git localement.
- Actions:
  - ajouter et versionner `api/`, `docs/`, `scripts/`, `README.md`, `plan.md` si ce sont bien les sources canoniques;
  - sinon retirer explicitement le statut canonique de la doc locale;
  - ajouter les workflows CI/deploy manquants dans le repo canonique.
- Critères d'acceptation:
  1. `git status` ne montre plus `README.md`, `api/`, `docs/`, `scripts/`, `plan.md` en non suivis.
  2. `.github/workflows/` existe réellement dans `crazy_life`.

## J7 — une semaine

### R-006 — Stabiliser l'observabilité machine dans le cockpit ops
- Priorité: **Haute**
- Problème: `ops_agent` n'est pas intégré à la synthèse et le statut GPU est faux.
- Actions:
  - corriger la remontée `ops_agent` dans `/api/ops/summary`;
  - rétablir `machine_logs` et `docker_events` si ces sources doivent exister;
  - réparer ou désactiver explicitement le probe GPU selon l'intention réelle.
- Critères d'acceptation:
  1. `/api/ops/summary` retourne `ops_agent` non nul.
  2. la vue ops reflète correctement l'activité GPU observée par `nvidia-smi`.

### R-007 — Rendre les builds hermétiques et non salissants
- Priorité: **Moyenne-Haute**
- Problème: le build de `mascarade/web` modifie des artefacts suivis.
- Actions:
  - décider si `api/public/*` doit être versionné ou généré;
  - ignorer les `tsbuildinfo` si ce sont des artefacts locaux;
  - séparer build local et artefacts destinés à publication.
- Critères d'acceptation:
  1. un `npm run build` ne modifie plus le worktree local.
  2. la politique d'artefacts est documentée pour `mascarade` et `crazy_life`.

### R-008 — Réduire la dérive locale de `Kill_LIFE`
- Priorité: **Moyenne-Haute**
- Problème: trop de modifications critiques locales rendent l'état réel difficile à auditer.
- Actions:
  - découper les modifications en branches/sujets cohérents;
  - isoler les suppressions/modifications de workflows;
  - versionner ou supprimer les dépendances vers `tools/ci_runtime.py` et `tools/scope_policy.py` non suivies;
  - rediriger les sorties d'audit/build vers un répertoire de preuves dédié non suivi au lieu de `docs/` et `docs/evidence/` par défaut;
  - produire un état publié ou une branche d'intégration auditée.
- Critères d'acceptation:
  1. les changements CI/CD, docs et tools sont séparés par PR/branche.
  2. aucun script suivi ne dépend de modules non suivis.
  3. le worktree n'est plus un mélange de dizaines de sujets.

### R-009 — Décider du sort de `ai-agentic-embedded-base`
- Priorité: **Moyenne-Haute**
- Problème: duplication structurelle persistante dans `Kill_LIFE`.
- Actions:
  - choisir entre vendoring assumé, sous-module, template externe, ou suppression de la duplication;
  - documenter quelle arborescence fait foi.
- Critères d'acceptation:
  1. une seule source de vérité est définie pour docs/tools/firmware dupliqués.
  2. les corrections ne nécessitent plus de double édition systématique.

## J30 — durable

### R-010 — Clarifier le contrat multi-repo
- Priorité: **Moyenne**
- Problème: le bridge `mascarade` <-> `crazy_life` existe encore alors que `crazy_life` est déclaré canonique.
- Actions:
  - décider si `scripts/sync_crazy_life.sh` reste un bridge supporté ou devient un outil de migration temporaire;
  - expliciter le rôle exact de chaque repo dans un document unique versionné;
  - retirer les documents contradictoires.
- Critères d'acceptation:
  1. aucune ambiguïté sur la source canonique du frontend, du backend cockpit et des workflows runtime.
  2. la documentation n'induit plus deux chemins de publication concurrents.

### R-011 — Renforcer la CI de `crazy_life` et `Kill_LIFE`
- Priorité: **Moyenne**
- Actions:
  - `crazy_life`: build web, build API, test API, publication contrôlée;
  - `Kill_LIFE`: environnement Python/firmware reproductible, lint/tests minimum, vérification des workflows.
- Critères d'acceptation:
  1. chaque repo a une CI bloquante adaptée à son rôle.
  2. les badges renvoient à des workflows effectivement présents dans le repo concerné.

### R-012 — Réduire la surface exposée au niveau hôte
- Priorité: **Moyenne**
- Actions:
  - inventorier précisément l'usage de `22`, `80`, `443`, `3389`;
  - appliquer une politique explicite de pare-feu ou d'écoute limitée au LAN/local;
  - documenter les services volontairement publics.
- Critères d'acceptation:
  1. chaque port public a un propriétaire et une justification.
  2. aucune écoute publique inutile ne subsiste.
