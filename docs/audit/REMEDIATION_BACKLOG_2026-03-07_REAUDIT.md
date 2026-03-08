# Remediation Backlog — Re-audit du 7 mars 2026

Backlog canonique issu du ré-audit courant. Ce document remplace les priorités implicites du rapport précédent sans écraser l'historique.

## J0 — immédiat

### RA-001 — Sérialiser le fine-tuning CPU
- Priorité: **Critique**
- Problème:
  - `3` jobs `train_cpu.py` restent actifs en parallèle alors que la machine consomme déjà `4.7 GiB` de swap.
- Actions:
  - imposer `1` seul `train_cpu.py` actif à la fois;
  - suspendre les lots non urgents tant que la RAM libre n'est pas redevenue suffisante;
  - geler cette règle dans le scheduler / wrappers fine-tuning.
- Critères d'acceptation:
  1. `ps --sort=-pmem` ne montre plus qu'un seul `train_cpu.py`;
  2. `free -h` montre un swap en baisse stable après retour au repos;
  3. les futures validations ops/tests se font hors pression mémoire extrême.

### RA-002 — Réactiver une auth runtime réelle sur `mascarade`
- Priorité: **Critique**
- Problème:
  - `MASCARADE_API_KEY` est vide et `/api/ops/summary` répond `200` sans token.
- Actions:
  - renseigner un secret fort non vide pour `MASCARADE_API_KEY`;
  - redémarrer la pile concernée;
  - vérifier via `edge-proxy` et via l'API directe qu'un appel sans token échoue;
  - distinguer ce secret de la matrice "provider API keys".
- Critères d'acceptation:
  1. `/api/ops/summary` retourne `401` ou `403` sans token;
  2. les tests / logs n'impriment plus le mode `all protected routes are PUBLIC`;
  3. le runtime n'expose plus `MASCARADE_API_KEY` vide.

### RA-003 — Réduire la surface hôte exposée tant que l'auth n'est pas solide
- Priorité: **Critique**
- Problème:
  - l'hôte publie encore `80/443/22/3389` alors que le cockpit ops reste accessible sans auth effective.
- Actions:
  - décider quels ports doivent réellement rester publics;
  - limiter au LAN ou au loopback ce qui n'a pas besoin d'être public;
  - documenter le propriétaire et la justification de chaque écoute restante.
- Critères d'acceptation:
  1. aucun endpoint ops non authentifié n'est accessible depuis le LAN;
  2. chaque port public restant a une justification documentée;
  3. le risque "proxy public + auth vide" est supprimé.

### RA-004 — Réparer le contrat `ops-agent` / `summary` / GPU
- Priorité: **Critique**
- Problème:
  - `ops-agent` et `/api/ops/sources` annoncent des sources disponibles que `/api/ops/summary` ne remonte pas.
- Actions:
  - corriger l'agrégation `ops-agent` dans `/api/ops/summary`;
  - réaligner `machine_logs`, `docker_events`, `docker_logs`, `ops_agent` et `gpu`;
  - décider explicitement si la source GPU doit être supportée ou désactivée.
- Critères d'acceptation:
  1. `/api/ops/sources` et `/api/ops/summary` racontent la même histoire;
  2. `ops_agent` n'est plus `null` si l'agent répond;
  3. l'état GPU reflète l'activité observée par `nvidia-smi`.

### RA-005 — Stabiliser le pipeline logs/history avant d'ajouter des couches
- Priorité: **Haute**
- Problème:
  - `logs/query` et `logs/recent` fonctionnent, mais `promtail` et `loki` journalisent encore des erreurs, et le stream peut servir des volumes massifs.
- Actions:
  - corriger les erreurs `promtail -> loki` encore visibles;
  - vérifier le comportement et les limites de `/api/ops/logs/stream`;
  - garder la distinction `recent` / `history` / `stream` claire dans l'API et dans l'UI.
- Critères d'acceptation:
  1. les erreurs `context deadline exceeded` et `scheduler EOF` ne reviennent plus en régime nominal;
  2. le mode stream ne déverse plus de payloads non bornés sans contrôle explicite;
  3. le mode `history` reste utilisable indépendamment du stream.

## J7 — une semaine

### RA-006 — Corriger la publication distante réelle de `crazy_life`
- Priorité: **Haute**
- Problème:
  - localement le repo est propre et testable, mais la cible GitHub `electron-rare/crazy_life` répond `404`.
- Actions:
  - confirmer le remote canonique réel;
  - corriger `origin` ou provisionner le dépôt attendu;
  - rerun `scripts/publish_preflight.sh probe-remote` jusqu'au vert.
- Critères d'acceptation:
  1. le probe remote ne retourne plus `404`;
  2. le chemin de publication canonique est documenté;
  3. le statut "repo publiable" repose sur un remote réel, pas seulement sur l'état local.

### RA-007 — Geler une commande bootstrap/test Python par repo
- Priorité: **Haute**
- Problème:
  - `mascarade/core` et `Kill_LIFE` échouent encore via `python3 -m pytest -q` sans bootstrap préalable.
- Actions:
  - définir une commande bootstrap documentée par repo;
  - définir une commande test unique et stable par repo;
  - rendre explicite l'usage du `.venv` repo quand c'est le chemin supporté.
- Critères d'acceptation:
  1. `mascarade` a une commande test Python documentée et reproductible;
  2. `Kill_LIFE` a une commande test Python documentée et reproductible;
  3. un opérateur ne doit plus deviner le bon interpréteur.

### RA-008 — Rendre `mascarade/web` non salissant
- Priorité: **Moyenne-Haute**
- Problème:
  - le build web modifie encore `api/public/*` et `web/tsconfig.tsbuildinfo`.
- Actions:
  - décider si `api/public` est un artefact généré ou une sortie versionnée;
  - ignorer ou déplacer `tsconfig.tsbuildinfo` si c'est un artefact local;
  - rendre le build reproductible sans modifier le worktree suivi.
- Critères d'acceptation:
  1. `npm --prefix web run build` ne change plus le worktree suivi;
  2. la politique d'artefacts est documentée;
  3. le repo n'accumule plus de bruit de build.

### RA-009 — Réduire la dérive locale de `Kill_LIFE`
- Priorité: **Moyenne-Haute**
- Problème:
  - le repo garde `37` entrées de statut local, dont un lot MCP encore fusionné dans le même delta.
- Actions:
  - découper les modifications en groupes publiables cohérents;
  - isoler la pile MCP des autres sujets documentaires / outils / spec;
  - réduire le worktree à des branches ou PRs lisibles.
- Critères d'acceptation:
  1. les changements MCP sont isolés dans un lot cohérent;
  2. le worktree n'est plus un mélange de dizaines de sujets;
  3. la publication / revue par sujet redevient possible.

### RA-010 — Requalifier la matrice secrets: requis vs optionnels
- Priorité: **Moyenne**
- Problème:
  - le backlog "remplir les vraies clés API" est devenu imprécis.
- Actions:
  - séparer les secrets requis pour la sécurité runtime (`MASCARADE_API_KEY`) des secrets providers et des secrets optionnels MCP/live;
  - documenter l'état attendu de `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NOTION_TOKEN`, `GITHUB_TOKEN`, etc.;
  - éviter les tickets vagues de type "tout remplir".
- Critères d'acceptation:
  1. chaque secret a un rôle et un niveau de criticité clairs;
  2. les tickets "missing secret" restants sont ciblés;
  3. `MASCARADE_API_KEY` n'est plus noyée dans la liste des providers.

## J30 — durable

### RA-011 — Clarifier le contrat multi-repo
- Priorité: **Moyenne**
- Actions:
  - figer le rôle exact de `mascarade`, `crazy_life` et `Kill_LIFE`;
  - retirer les formulations encore contradictoires entre "repo canonique", bridge et companion repo;
  - expliciter le chemin de publication par surface.
- Critères d'acceptation:
  1. une seule source de vérité par surface;
  2. plus de confusion entre local bridge et repo canonique.

### RA-012 — Renforcer CI et release autour des chemins canoniques réels
- Priorité: **Moyenne**
- Actions:
  - faire correspondre badges, workflows et repos réellement publiés;
  - valider les preflights publication sur les vrais remotes;
  - éviter les workflows "verts localement mais sans cible distante".
- Critères d'acceptation:
  1. la CI renvoie aux repos et remotes corrects;
  2. les checks bloquants couvrent build/test/publication utile.

### RA-013 — Différer les validations E2E non critiques jusqu'à stabilisation
- Priorité: **Moyenne**
- Actions:
  - garder en attente les lots `batch fine-tuning completed` et `n8n import E2E` tant que `RA-001` à `RA-008` ne sont pas sous contrôle;
  - éviter d'utiliser des validations E2E comme substitut à la stabilisation runtime.
- Critères d'acceptation:
  1. les E2E reprennent sur une machine stabilisée;
  2. les résultats E2E redeviennent interprétables.

## Items requalifiés depuis le backlog précédent

- `crazy_life`:
  - ancien problème "repo local non publiable" -> **réduit**
  - nouveau vrai problème: **remote GitHub non résolu**
- `/api/ops/logs/query`:
  - ancien problème "route à finir" -> **obsolète**
  - nouveau vrai problème: **stabilisation et bornage du pipeline logs**
- "remplir les vraies clés API":
  - ancien ticket global -> **à découper**
  - nouveau vrai problème: **sécurité runtime + matrice secrets ciblée**
