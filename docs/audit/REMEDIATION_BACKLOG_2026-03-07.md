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
- Etat audit 7 mars: le middleware auth est **implemente** (`api/src/middleware/auth.ts`, timing-safe, bearer+cookie, multi-cle) mais **desactive** car `.env` contient `MASCARADE_API_KEY=""`.
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
- **Etat audit 7 mars: RESOLU.**
  - `git status` propre (clean, up-to-date with origin/main).
  - `.github/workflows/` present avec `ci.yml` et `deploy-pages.yml`.
  - `README.md` versionne avec references ecosysteme.
  - `scripts/deploy_local.sh` versionne.
  - Le repo ne contient pas `api/` ni `docs/` (frontend-only, c'est normal).
- ~~Actions~~: aucune action restante.

## J7 — une semaine

### R-006 — Stabiliser l'observabilité machine dans le cockpit ops
- Priorité: **Haute**
- Etat audit 7 mars: `ops-agent` est **complet** (/health, /sources, /summary, /logs/recent, /logs/stream). Collecte Docker + journald fonctionnelle. Mais **aucun probe GPU** (nvidia-smi) n'existe cote ops-agent ni cote API.
- Actions restantes:
  - ajouter un probe GPU (nvidia-smi) dans ops-agent ou dans `/api/ops/summary`;
  - verifier que `/api/ops/summary` remonte correctement les donnees ops-agent.
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

Cette section sert de bloc `DIFFERE (post-stabilisation)` pour les sujets a ouvrir
apres mise sous controle des remediations `J0` et `J7`.

References de detail:
- Workflow Editor: [plan.md](../../plan.md), [plan.md](../../../crazy_life/plan.md)
- Fine-tuning: [TODO_TUNNING_PARTY.md](../../TODO_TUNNING_PARTY.md), [README.md](../../finetune/README.md)
- KiCad MCP: [kicad_mcp_scope_spec.md](../../../Kill_LIFE/specs/kicad_mcp_scope_spec.md), [ROADMAP.md](../../finetune/kicad_mcp_server/docs/ROADMAP.md)

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
- Dépendance post-stabilisation:
  - ouvrir ce chantier apres fermeture ou mise sous controle de `R-001` a `R-009`.

### R-011 — Renforcer la CI de `crazy_life` et `Kill_LIFE`
- Priorité: **Moyenne**
- Problème: la publication canonique reste insuffisamment protegee par des checks
  repo-locaux coherents entre `crazy_life` et `Kill_LIFE`.
- Actions:
  - `crazy_life`: build web, build API, test API, publication contrôlée;
  - `Kill_LIFE`: environnement Python/firmware reproductible, lint/tests minimum, vérification des workflows.
- Critères d'acceptation:
  1. chaque repo a une CI bloquante adaptée à son rôle.
  2. les badges renvoient à des workflows effectivement présents dans le repo concerné.
- Dépendance post-stabilisation:
  - ouvrir ce chantier apres stabilisation du chemin de publication canonique et de la cartographie multi-repo.

### R-012 — Réduire la surface exposée au niveau hôte
- Priorité: **Moyenne**
- Problème: des ports et services restent exposes alors que leur ownership exact,
  leur cible reseau et leur necessite publique ne sont pas encore figes.
- Actions:
  - inventorier précisément l'usage de `22`, `80`, `443`, `3389`;
  - appliquer une politique explicite de pare-feu ou d'écoute limitée au LAN/local;
  - documenter les services volontairement publics.
- Critères d'acceptation:
  1. chaque port public a un propriétaire et une justification.
  2. aucune écoute publique inutile ne subsiste.
- Dépendance post-stabilisation:
  - ouvrir ce chantier apres reactivation d'une authentification effective et stabilisation du cockpit ops.

### R-013 — Workflow Editor Lot 2
- Priorité: **Moyenne**
- Problème: le lot 2 de l'editeur workflow est encore disperse entre backlog
  produit et execution multi-repo, sans cadrage transverse unique.
- Actions:
  - limiter `Blockly` aux noeuds de logique avancee et garder [plan.md](../../plan.md) comme detail produit;
  - ajouter l'import assiste depuis `docs/workflows/*.md` en mode brouillon seulement, jamais en overwrite direct;
  - ajouter un diff visuel avant save et un historique multi-version sans changer le format canonique `Kill_LIFE/workflows/*.json`;
  - documenter tout changement de contrat `/api/killlife/*` avant extension de surface.
- Critères d'acceptation:
  1. `Blockly` reste borne aux cas de logique avancee et ne remplace pas le graphe canonique.
  2. l'import depuis `docs/workflows/*.md` cree un draft explicite avant tout save.
  3. un diff visuel est disponible avant ecriture du JSON canonique.
  4. le lot 2 ne cree pas de nouveau format de workflow concurrent.
- Dépendance post-stabilisation:
  - ouvrir ce chantier apres clarification du contrat multi-repo et gel d'un chemin publiable pour `crazy_life`.
- Références:
  - [plan.md](../../plan.md)
  - [plan.md](../../../crazy_life/plan.md)

### R-014 — Fine-tuning hors pipeline critique
- Priorité: **Moyenne-Basse**
- Problème: les sujets exploratoires autour du fine-tuning local et d'`Agent Zero`
  existent deja, mais ils ne doivent pas reouvrir le chemin critique tant que le runtime principal n'est pas stabilise.
- Actions:
  - cadrer l'evaluation d'`Agent Zero` hors du pipeline critique a partir de [TODO_TUNNING_PARTY.md](../../TODO_TUNNING_PARTY.md);
  - definir un job isole, reproductible et non bloquant pour comparer baseline et candidat;
  - versionner les resultats d'evaluation et les runbooks utiles dans la doc `finetune`;
  - interdire toute dependance obligatoire nouvelle dans le chemin critique sans decision explicite.
- Critères d'acceptation:
  1. un protocole d'evaluation isole existe avec baseline, jeu de taches et mesure documentes.
  2. les resultats sont versionnes sans devenir un prerequis de production.
  3. aucune etape du pipeline critique ne depend d'`Agent Zero` par defaut.
  4. le runbook operateur `finetune` reste executable sans activer ce chantier.
- Dépendance post-stabilisation:
  - ouvrir ce chantier seulement apres validation d'un run batch complet et gel du runbook operateur fine-tuning.
- Références:
  - [TODO_TUNNING_PARTY.md](../../TODO_TUNNING_PARTY.md)
  - [README.md](../../finetune/README.md)

### R-015 — KiCad MCP roadmap v2+
- Priorité: **Moyenne-Basse**
- Problème: les idees `Digikey`, BOM smart, design patterns et auto-routing
  depassent le contrat `KiCad MCP v1` et doivent rester opt-in tant que la surface stable n'est pas entierement consolidee.
- Actions:
  - decomposer chaque capability v2+ dans une spec dediee a partir de [kicad_mcp_scope_spec.md](../../../Kill_LIFE/specs/kicad_mcp_scope_spec.md);
  - garder le serveur `kicad` v1 stable comme unique surface par defaut;
  - ajouter un smoke et un garde-fou specifiques avant toute promotion d'une capability v2+;
  - documenter les dependances externes futures (`Digikey`, sourcing avance, routing assiste) dans la roadmap du serveur.
- Critères d'acceptation:
  1. chaque capability v2+ a une spec propre, un owner et un smoke dedie.
  2. aucun elargissement silencieux du contrat `kicad` v1 n'est introduit.
  3. les smokes v1 restent verts a l'identique apres ajout de features v2+.
  4. les dependances externes et secrets nouveaux sont explicites avant implementation.
- Dépendance post-stabilisation:
  - ouvrir ce chantier apres stabilisation complete de la pile MCP supportee et validation du runtime canonique sur hote + conteneur.
- Références:
  - [kicad_mcp_scope_spec.md](../../../Kill_LIFE/specs/kicad_mcp_scope_spec.md)
  - [ROADMAP.md](../../finetune/kicad_mcp_server/docs/ROADMAP.md)
