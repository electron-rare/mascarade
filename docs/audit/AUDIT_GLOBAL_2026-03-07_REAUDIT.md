# Re-audit Global Machine + Repos — 2026-03-07 (21:32 CET)

## Résumé exécutif

Ré-audit non intrusif effectué sur l'hôte `Tower`, la stack Docker locale, et les dépôts `/home/clems/mascarade`, `/home/clems/crazy_life` et `/home/clems/Kill_LIFE`.

Constat global courant:

- Le risque d'exploitation reste **élevé** côté `mascarade` tant que `MASCARADE_API_KEY` reste vide et que l'hôte publie toujours `80/443`.
- La pression machine reste **critique**: `25 GiB / 31 GiB` de RAM utilisés, `4.7 GiB / 8 GiB` de swap utilisés, et `3` jobs `train_cpu.py` consomment chacun environ `6.7` à `7.3 GiB` RSS.
- L'observabilité `mascarade` a partiellement progressé: `/api/ops/logs/query` et `/api/ops/logs/recent` répondent, mais le contrat `ops-agent` reste incohérent entre `/health`, `/sources` et `/summary`.
- `crazy_life` s'est nettement amélioré localement: worktree propre, workflows suivis, tests API et build web passent. En revanche, la publication distante reste bloquée: le probe GitHub de `electron-rare/crazy_life` retourne toujours `404`.
- `Kill_LIFE` reste fortement modifié localement (`37` entrées dans `git status --short`), mais la situation MCP est meilleure que lors de l'audit précédent: les smokes `kicad` et `validate-specs` passent, et `notion` / `github-dispatch` ne sont plus bloqués que par l'absence de secrets live.

## Portée et méthode

Vérifications exécutées pendant ce tour:

- hôte: `date`, `free -h`, `ps`, `ss -lntp`, `nvidia-smi`
- Docker: `docker ps`, `docker inspect`, `docker logs`
- probes HTTP locaux: `/health`, `/api/ops/summary`, `/api/ops/sources`, `/api/ops/logs/recent`, `/api/ops/logs/query`, `ops-agent /health`, `ops-agent /sources`
- Git: `git status --short`, `git diff --name-only`, `git remote -v`
- builds/tests:
  - `mascarade/api`: `npm test`, `npm run build`
  - `mascarade/web`: `npm run build`
  - `mascarade/core`: `.venv/bin/python -m pytest -q`, puis `python3 -m pytest -q`
  - `crazy_life/api`: `npm test`, `npm run build`
  - `crazy_life/web`: `npm run build`
  - `Kill_LIFE`: `python3 -m pytest -q`, `python3 -m unittest discover -s test -p 'test_*.py'`, `python3 tools/validate_specs.py --json`, smokes MCP

Le but de ce ré-audit est de revalider l'état courant, pas de recycler automatiquement les constats du rapport précédent.

## Findings priorisés

### F-001 — La pression mémoire/swap reste critique sur l'hôte

- Sévérité: **Critique**
- Détails:
  - `free -h`: `25 GiB` RAM utilisés, `2.2 GiB` libres, `4.7 GiB` de swap utilisés.
  - `ps` hôte: `3` processus `train_cpu.py` actifs (`emc`, `platformio`, `embedded`) utilisent chacun ~`20.6%` à `22.4%` mémoire et ~`6.7` à `7.3 GiB` RSS.
  - `nvidia-smi`: `ollama` occupe ~`2364 MiB / 5120 MiB` GPU, avec `100%` d'utilisation GPU.
- Impact:
  - temps de réponse moins fiables;
  - validation d'audit et de tests polluée par l'état machine;
  - risque persistant de swap storm / latence globale.

### F-002 — `mascarade` répond toujours sans authentification effective

- Sévérité: **Critique**
- Détails:
  - le fichier `.env` courant garde `MASCARADE_API_KEY` vide;
  - `curl http://127.0.0.1/api/ops/summary` retourne `HTTP 200`;
  - `curl http://127.0.0.1:3100/api/ops/summary` retourne aussi `HTTP 200`;
  - les tests API consignent explicitement le mode `all protected routes are PUBLIC`.
- Impact:
  - les routes `/api/*` restent appelables sans token tant que l'API est exposée via le proxy;
  - l'état ops complet est consultable depuis le LAN.

### F-003 — La surface hôte publiée reste supérieure au strict besoin

- Sévérité: **Haute**
- Détails:
  - `ss -lntp` expose toujours `0.0.0.0:80`, `0.0.0.0:443`, `0.0.0.0:22` et `*:3389`;
  - les logs `edge-proxy` montrent des requêtes LAN réelles vers `http://192.168.0.120/...`;
  - des accès répétés à `/api/ops/summary`, `/api/ops/sources` et `/api/ops/logs/stream` sont visibles.
- Impact:
  - le défaut d'auth n'est pas seulement théorique;
  - la pile reste observable depuis le LAN tant que le proxy est ouvert.

### F-004 — Le contrat d'observabilité reste incohérent entre `ops-agent` et l'API

- Sévérité: **Haute**
- Détails:
  - `ops-agent /health` retourne `{"docker": true, "journald": true, "gpu": false}`;
  - `ops-agent /sources` annonce `docker_logs`, `docker_events`, `journald` et `loki` disponibles;
  - `/api/ops/sources` confirme `machine_logs`, `docker_events`, `docker_logs`, `loki_history` et `otel` disponibles;
  - `/api/ops/summary` retourne pourtant `machine_logs: false`, `docker_events: false` et `ops_agent: null`;
  - `nvidia-smi` montre pourtant `ollama` actif sur GPU alors que la source GPU est reportée comme indisponible.
- Impact:
  - la vue cockpit ne reflète pas fidèlement l'état machine;
  - les opérateurs ne peuvent pas se fier à `summary` pour l'état réel des sources ops.

### F-005 — La chaîne logs/history est partiellement rétablie, mais reste dégradée

- Sévérité: **Haute**
- Détails:
  - `/api/ops/logs/query?limit=5` répond correctement avec une source `loki`;
  - `/api/ops/logs/recent?limit=5` répond correctement avec des entrées `machine` et `service`;
  - `promtail` journalise encore `context deadline exceeded` vers `loki`;
  - les entrées récentes incluent des erreurs Loki (`error sending requests to scheduler`, `EOF`);
  - `edge-proxy` sert un stream `/api/ops/logs/stream` de taille très importante (`52300773` octets dans l'échantillon consulté).
- Impact:
  - le blocage n'est plus "la route n'existe pas";
  - le vrai sujet est maintenant la robustesse du pipeline logs et le coût du mode stream.

### F-006 — `crazy_life` est presque réhabilité localement, mais pas publiable à distance

- Sévérité: **Haute**
- Détails:
  - `git status --short`: worktree propre;
  - workflows suivis présents: `ci.yml`, `deploy-pages.yml`;
  - `npm --prefix api test` passe;
  - `npm run build` passe côté web sans salir le worktree;
  - `scripts/publish_preflight.sh status` est vert localement;
  - `scripts/publish_preflight.sh probe-remote` échoue encore avec `HTTP 404` sur `electron-rare/crazy_life`.
- Impact:
  - le problème n'est plus le repo local;
  - le blocage est désormais le chemin de publication / la cible GitHub réelle.

### F-007 — Les tests Python restent reproductibles seulement via chemins implicites

- Sévérité: **Moyenne-Haute**
- Détails:
  - `mascarade/core`: `.venv/bin/python -m pytest -q` passe, mais `python3 -m pytest -q` échoue avec `No module named pytest`;
  - `Kill_LIFE`: `python3 -m pytest -q` échoue avec `No module named pytest`;
  - `Kill_LIFE`: `python3 -m unittest discover -s test -p 'test_*.py'` passe (`10` tests);
  - `Kill_LIFE`: `python3 tools/validate_specs.py --json` passe.
- Impact:
  - les procédures de test restent dépendantes d'une connaissance implicite du bon interpréteur;
  - la reproductibilité sur machine fraîche n'est pas encore gelée.

### F-008 — La dérive de build s'est améliorée, mais `mascarade` n'est pas encore hermétique

- Sévérité: **Moyenne**
- Détails:
  - `crazy_life` build web/API sans modifier le worktree;
  - `mascarade/api` test et build passent;
  - `mascarade/web` build passe, mais modifie encore des artefacts suivis:
    - `api/public/index.html`
    - remplacement de l'asset JS versionné
    - `web/tsconfig.tsbuildinfo`
- Impact:
  - le problème "build salissant" n'est plus général à tous les repos;
  - il reste concentré sur `mascarade/web`.

### F-009 — `Kill_LIFE` reste très modifié localement, mais certains risques du précédent audit sont résolus

- Sévérité: **Moyenne-Haute**
- Détails:
  - `git status --short | wc -l`: `37` entrées;
  - `git diff --name-only | wc -l`: `15` chemins suivis modifiés;
  - les modules `tools/ci_runtime.py` et `tools/scope_policy.py` sont maintenant bien suivis par Git;
  - smokes MCP:
    - `kicad`: `ready`
    - `validate-specs`: `ready`
    - `notion`: `degraded` uniquement faute de secret
    - `github-dispatch`: `degraded` uniquement faute de token
- Impact:
  - la dérive locale reste réelle;
  - mais la situation MCP est plus mature et moins "promesse cassée" que lors du rapport précédent.

## Delta depuis l'audit précédent du 7 mars 2026

### Résolu ou nettement réduit

- `crazy_life` n'a plus le profil "repo canonique non versionné localement":
  - workflows, `README`, `api`, `docs`, `scripts`, `plan.md` sont présents et suivis;
  - build web et tests API passent;
  - worktree propre après build.
- `Kill_LIFE` ne dépend plus de modules non suivis pour `ci_runtime` / `scope_policy`.
- la pile MCP locale n'est plus en état "docs > runtime":
  - `kicad` et `validate-specs` passent réellement;
  - `notion` / `github-dispatch` existent réellement et échouent seulement en mode live faute de secret.
- `/api/ops/logs/query` et `/api/ops/logs/recent` sont désormais opérationnels.

### Toujours vrai

- saturation mémoire/swap due au fine-tuning concurrent;
- `MASCARADE_API_KEY` vide et API accessible sans auth;
- exposition hôte `80/443/22/3389`;
- commandes Python "naturelles" non reproductibles sans bootstrap explicite.

### Partiellement amélioré mais non résolu

- faux verts ops:
  - moins de rupture fonctionnelle qu'au précédent audit,
  - mais incohérence persistante entre `ops-agent`, `/api/ops/sources` et `/api/ops/summary`;
- build salissant:
  - `crazy_life` corrigé,
  - `mascarade/web` encore salissant.

### Obsolète ou à requalifier

- "Finir `/api/ops/logs/query`" n'est plus la bonne formulation:
  - la route existe et répond;
  - il faut maintenant la stabiliser et la rendre cohérente avec le mode stream/history.
- "Geler l'état publiable de `crazy_life`" doit être requalifié:
  - le problème n'est plus le repo local;
  - le blocage est le remote GitHub cible (`404`).
- "Remplir les vraies clés API dans `.env`" est trop grossier:
  - `MISTRAL_API_KEY` est déjà présente;
  - `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `NOTION_TOKEN` restent absents;
  - `MASCARADE_API_KEY` reste vide et doit être traité à part comme exigence de sécurité runtime.

## Séquence recommandée

1. remettre la machine sous contrôle (`train_cpu.py` concurrent -> 1 max);
2. réactiver une auth effective `mascarade` et revalider `401` via proxy;
3. corriger le contrat `ops-agent` / `summary` / GPU avant d'empiler plus d'observabilité;
4. réduire ou justifier l'exposition hôte tant que l'auth n'est pas solide;
5. corriger le remote GitHub réel de `crazy_life`;
6. standardiser les commandes bootstrap/test Python par repo;
7. rendre `mascarade/web` non salissant;
8. seulement ensuite rouvrir les lots E2E secondaires (`Kill_LIFE` import n8n, validation batch fine-tuning complète, etc.).
