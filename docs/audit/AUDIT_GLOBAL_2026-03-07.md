# Audit Global Machine + Repos — 2026-03-07

## Résumé exécutif
Audit non intrusif réalisé sur la machine `Tower` et les dépôts `/home/clems/mascarade`, `/home/clems/Kill_LIFE` et `/home/clems/crazy_life`, avec collecte d'évidence locale et exécution de builds/tests non destructifs.

Constat global:
- Le runtime Docker est largement disponible: `24` conteneurs `Up`, dont `18` avec healthcheck `healthy`.
- La machine est sous forte pression de ressources à cause de jobs de fine-tuning CPU concurrents et d'un runner Ollama déjà chargé.
- `mascarade` fonctionne en production locale, mais plusieurs signaux d'exploitation sont contradictoires: healthchecks verts, erreurs applicatives récurrentes, observabilité machine incomplète et route ops accessible sans auth.
- `crazy_life` compile localement, mais le repo local n'est pas publiable en l'état: une partie structurante du backend/docs/scripts n'est pas suivie par Git.
- `Kill_LIFE` a une très large dérive locale sur les workflows, la doc et les outils; l'environnement de test Python n'est pas encore pleinement reproductible localement.

Niveau de risque global: **Élevé** pour la fiabilité opérationnelle et la gouvernance multi-repo, **Élevé** pour la sécurité locale tant que `mascarade` répond sans auth effective sur des ports publics.

## Portée et méthode
- Audit hôte: OS, ressources, réseau, services, Docker, GPU, journaux récents.
- Audit `mascarade`: Git, compose, runtime, builds/tests, observabilité, sécurité d'accès.
- Audit `Kill_LIFE`: Git, workflows, duplication, tests/checks disponibles, cohérence opérationnelle.
- Audit `crazy_life`: Git, builds/tests, CI, état de publication, couplage avec `Kill_LIFE`.
- Les preuves brutes sont sous `docs/audit/AUDIT_EVIDENCE_2026-03-07/`.

## Points positifs
1. La stack runtime locale répond globalement bien.
   - Preuves: `docker_status_compact.txt`, `docker_health_compact.txt`, `mascarade_api_health.json`, `mascarade_core_health.json`
2. Les builds TypeScript/React de `mascarade` et `crazy_life` passent localement.
   - Preuves: `mascarade_api_build.txt`, `mascarade_api_test.txt`, `mascarade_web_build.txt`, `crazy_life_api_build.txt`, `crazy_life_api_test.txt`, `crazy_life_web_build.txt`
3. Le contrôle compliance strict de `Kill_LIFE` passe.
   - Preuve: `kill_life_compliance_validate.txt`
4. Le scan léger de patterns sensibles sur fichiers suivis n'a pas trouvé de secret évident.
   - Preuves: `mascarade_sensitive_pattern_files.txt`, `kill_life_sensitive_pattern_files.txt`, `crazy_life_sensitive_pattern_files.txt`

## Findings priorisés

### F-001 — Saturation mémoire/swap et charge CPU durable sur l'hôte
- Sévérité: **Critique**
- Impact: ralentissements transverses, timeouts applicatifs, builds/tests moins fiables, risque d'OOM ou d'effondrement de latence.
- Détails:
  - Snapshot hôte: `31 GiB` RAM totale, `28 GiB` utilisée, `6.6 GiB / 8 GiB` de swap consommée.
  - Plusieurs processus `train_cpu.py` monopolisent chacun ~14 à 16% mémoire et >120% CPU.
  - `ollama` consomme déjà ~`2364 MiB` GPU sur une Quadro P2000 de `5120 MiB`.
- Preuves:
  - `host_free_h.txt`
  - `host_top_mem_processes.txt`
  - `host_top_cpu_processes.txt`
  - `host_nvidia_smi.txt`

### F-002 — Surface réseau publique supérieure au strict besoin applicatif
- Sévérité: **Haute**
- Impact: surface d'attaque élargie et exposition de services non strictement nécessaires à l'usage local.
- Détails:
  - Écoutes publiques observées sur `0.0.0.0:80`, `0.0.0.0:443`, `0.0.0.0:22` et `*:3389`.
  - Le reverse proxy répond directement sur `http://127.0.0.1/` et `https://127.0.0.1/`.
  - L'hôte porte l'IP LAN `192.168.0.120`.
- Preuves:
  - `host_listen_ports.txt`
  - `host_http_root_headers.txt`
  - `host_https_root_headers.txt`
  - `host_ip_addresses.txt`

### F-003 — `mascarade` expose ses routes API protégées en mode public
- Sévérité: **Critique**
- Impact: toute exposition via `80/443` augmente le risque d'appel non authentifié vers les routes `/api/*`.
- Détails:
  - La variable `MASCARADE_API_KEY` est déclarée mais vide dans l'environnement runtime de `mascarade-api`.
  - Les tests consignent explicitement: `all protected routes are PUBLIC`.
  - Un appel sans header à `http://127.0.0.1/api/ops/summary` retourne `HTTP/1.1 200 OK` avec un payload ops complet.
- Preuves:
  - `mascarade_api_runtime_env_selected.txt`
  - `mascarade_api_key_nonempty.txt`
  - `mascarade_api_test.txt`
  - `mascarade_ops_summary_noauth.txt`
  - code: `api/src/middleware/auth.ts`

### F-004 — Les healthchecks sont globalement verts, mais les logs montrent des échecs applicatifs répétés
- Sévérité: **Haute**
- Impact: faux sentiment de disponibilité; la stack peut rester "healthy" tout en échouant sur des flux réels.
- Détails:
  - `mascarade-core` journalise des `RuntimeError: All fallback attempts failed`.
  - `promtail` rencontre des `context deadline exceeded` vers Loki.
  - `edge-proxy` journalise des `upstream timed out` sur `/api/ops/logs/stream`.
  - La vue ops montre `ollama.error_rate = 5.96` avec `18` échecs fallback.
- Preuves:
  - `mascarade_docker_logs_key_signals.txt`
  - `mascarade_api_ops_summary.json`
  - `mascarade_api_ops_monitor.json`
  - `docker_health_compact.txt`

### F-005 — L'observabilité machine/GPU est partiellement dégradée dans la vue ops
- Sévérité: **Moyenne-Haute**
- Impact: le cockpit ops ne représente pas fidèlement l'état réel de la machine, donc le diagnostic distant est trompeur.
- Détails:
  - `ops_agent_health.json` annonce `docker: true`, `journald: true`, mais `gpu: false`.
  - En parallèle, `nvidia-smi` montre `ollama` actif sur GPU.
  - La synthèse `/api/ops/summary` déclare `machine_logs: false`, `docker_events: false`, `ops_agent: null`.
- Preuves:
  - `ops_agent_health.json`
  - `host_nvidia_smi.txt`
  - `mascarade_api_ops_summary.json`
  - `mascarade_api_ops_monitor.json`

### F-006 — `mascarade` a une chaîne Python locale ambiguë et dépendante du `.venv` repo
- Sévérité: **Moyenne**
- Impact: le composant central Python est testable, mais la commande "naturelle" échoue et la procédure locale n'est pas auto-évidente.
- Détails:
  - `python3 -m pytest -q` échoue dans `core/` avec `No module named pytest`.
  - Le repo-local `.venv` permet en revanche d'exécuter la suite `core/` avec succès (`109` tests observés via la sortie `-q`).
  - Le workflow de bootstrap/test n'est donc pas suffisamment explicite ni homogène avec les checks système.
- Preuves:
  - `mascarade_core_pytest_q.txt`
  - `mascarade_core_pytest_venv.txt`
  - `mascarade_package_scripts.txt`
  - `mascarade_test_files_named.txt`
  - `core/pyproject.toml`

### F-007 — Les builds de `mascarade` salissent le repo suivi
- Sévérité: **Moyenne-Haute**
- Impact: build non hermétique, difficultés de release propre, risque de commits accidentels d'artefacts.
- Détails:
  - Le snapshot initial montrait déjà un drift suivi (`README.md`, `scripts/sync_crazy_life.sh`, `web/README.md`).
  - Le build web modifie `api/public/index.html`, remplace un asset JS suivi et met à jour `web/tsconfig.tsbuildinfo`.
  - Le snapshot post-check montre en plus d'autres modifications locales hors build (`finetune/*` notamment), signe d'un workspace non stabilisé pendant l'audit.
- Preuves:
  - `mascarade_git_status.txt`
  - `mascarade_git_status_post_checks.txt`
  - `mascarade_git_diff_stat_post_checks.txt`
  - `mascarade_web_build.txt`

### F-008 — `crazy_life` n'est pas publiable comme repo canonique dans son état Git actuel
- Sévérité: **Critique**
- Impact: le repo se présente comme canonique, mais l'état suivi Git ne contient pas encore plusieurs éléments essentiels à sa reproductibilité.
- Détails:
  - `crazy_life` annonce être le repo canonique du cockpit.
  - Le build frontend et les tests API passent localement, mais `README.md`, `api/`, `docs/`, `scripts/` et `plan.md` ne sont pas suivis par Git localement.
  - Aucun workflow GitHub n'est suivi dans `.github/workflows` au moment de l'audit local.
- Preuves:
  - `crazy_life_git_status.txt`
  - `crazy_life_git_metrics.txt`
  - `crazy_life_github_workflows.txt`
  - `crazy_life_api_build.txt`
  - `crazy_life_api_test.txt`
  - `crazy_life_web_build.txt`
  - code/docs: `crazy_life/README.md`, `crazy_life/plan.md`

### F-009 — La couverture de tests de `crazy_life` reste mince et concentrée sur une seule zone backend
- Sévérité: **Moyenne**
- Impact: régressions UI et gateway non détectées facilement avant publication.
- Détails:
  - Un seul fichier de test nommé est détecté: `api/src/lib/killlife.test.ts`.
  - Aucun test frontend n'est visible dans l'état local suivi.
  - Le repo local n'a pas de workflow CI suivi, malgré les badges/documentation de repo canonique.
- Preuves:
  - `crazy_life_test_files_named.txt`
  - `crazy_life_github_workflows.txt`
  - `crazy_life_api_test.txt`

### F-010 — `Kill_LIFE` a une dérive locale massive sur des zones critiques de gouvernance
- Sévérité: **Haute**
- Impact: auditabilité réduite, CI/CD potentiellement instable, difficulté à savoir quel état fait autorité.
- Détails:
  - `78` chemins modifiés et `15` non suivis dans le snapshot local.
  - Les deltas touchent des workflows GitHub, le `README`, le `Makefile`, la conformité, l'évidence et les outils de build.
  - Des suppressions locales touchent des workflows d'audit/publication (`ci_cd_audit.yml`, `pages_publish.yml`) alors que d'autres workflows sont modifiés simultanément.
  - Plusieurs scripts suivis importent `tools/ci_runtime.py` et `tools/scope_policy.py`, alors que ces modules sont eux-mêmes non suivis localement.
  - Des commandes de vérification écrivent directement sous `docs/` et `docs/evidence/`, ce qui mélange état source et artefacts d'audit.
- Preuves:
  - `kill_life_git_status.txt`
  - `kill_life_git_metrics.txt`
  - `kill_life_git_diff_stat.txt`
  - `kill_life_github_workflows.txt`
  - `kill_life_untracked_module_imports.txt`
  - `kill_life_docs_writes_scan.txt`

### F-011 — `Kill_LIFE` a une chaîne de test locale non homogène
- Sévérité: **Moyenne-Haute**
- Impact: régressions Python probables non détectées localement; la conformité seule ne remplace pas les tests.
- Détails:
  - `python3 -m pytest -q` échoue avec `No module named pytest`.
  - Un test `unittest` ciblé (`test_setup_repo_dry_run.py`) passe via `unittest discover`, ce qui confirme qu'une partie de la suite est saine mais pas intégrée derrière une commande unique.
  - La validation compliance stricte passe, mais ce n'est pas une couverture fonctionnelle.
  - Le repo contient au moins `10` fichiers de test nommés, avec Python et firmware natif, sans bootstrap test unifié documenté dans l'environnement courant.
- Preuves:
  - `kill_life_pytest.txt`
  - `kill_life_unittest_discover_setup_repo.txt`
  - `kill_life_compliance_validate.txt`
  - `kill_life_test_files_named.txt`

### F-012 — `Kill_LIFE` porte une duplication structurelle importante avec `ai-agentic-embedded-base`
- Sévérité: **Moyenne-Haute**
- Impact: coûts de maintenance élevés, divergence documentaire probable, corrections à répliquer dans deux arbres.
- Détails:
  - Le repo contient un sous-arbre `ai-agentic-embedded-base` avec `docs/`, `hardware/`, `tools/`, `firmware/` et workflows similaires.
  - Le diff local touche en parallèle des fichiers racine et leurs équivalents sous `ai-agentic-embedded-base`.
- Preuves:
  - `kill_life_git_diff_stat.txt`
  - `kill_life_github_workflows.txt`
  - inventaire Git: `kill_life` suivi sous `docs/`, `tools/`, `ai-agentic-embedded-base/`

### F-013 — Le découpage multi-repo reste fortement couplé au filesystem local et au bridge historique
- Sévérité: **Moyenne-Haute**
- Impact: portabilité faible, tests d'intégration dépendants d'un chemin absolu, responsabilités encore ambiguës.
- Détails:
  - `crazy_life/api` pointe par défaut vers `/home/clems/Kill_LIFE` et `electron-rare/Kill_LIFE`.
  - `mascarade` conserve `scripts/sync_crazy_life.sh`, qui peut pousser ou réinjecter `web/` via bridge.
  - La cartographie documentaire décrit `crazy_life` comme canonique, mais le bridge `mascarade/web` reste toujours opérant et suivi.
- Preuves:
  - `cross_repo_bridge_refs.txt`
  - `cross_repo_cartography_refs.txt`
  - code/docs: `crazy_life/api/src/index.ts`, `crazy_life/api/src/lib/killlife.ts`, `mascarade/scripts/sync_crazy_life.sh`, `crazy_life/docs/REPO_CARTOGRAPHY_2026-03-07.md`

## Résultats des checks exécutés

| Cible | Commande | Résultat |
| --- | --- | --- |
| `mascarade/api` | `npm run build` | OK |
| `mascarade/api` | `npm test` | OK, `17` tests |
| `mascarade/web` | `npm run build` | OK |
| `mascarade/core` | `python3 -m pytest -q` | Échec, `pytest` absent du Python système |
| `mascarade/core` | `.venv/bin/python -m pytest -q` | OK via venv repo-local, `109` tests observés |
| `crazy_life/api` | `npm run build` | OK |
| `crazy_life/api` | `npm test` | OK, `11` tests |
| `crazy_life` | `npm run build` | OK |
| `Kill_LIFE` | `python3 -m pytest -q` | Échec, `pytest` absent |
| `Kill_LIFE` | `python3 -m unittest discover -s test -p "test_setup_repo_dry_run.py"` | OK, `1` test |
| `Kill_LIFE` | `python3 tools/compliance/validate.py --strict` | OK |

## Limites de l'audit
1. Le scan secrets est volontairement léger et ne remplace pas une SCA/CVE complète ni un scan secret outillé type `gitleaks`.
2. L'audit n'inclut pas de stress test; les constats de charge sont basés sur le snapshot réel pendant exécution.
3. L'hôte était vivant et modifié pendant l'audit, donc certains deltas Git représentent aussi une activité locale en cours.

## Synthèse
La machine et `mascarade` restent opérables, mais pas dans un état "sain et prévisible" au sens exploitation stricte. Le risque immédiat vient surtout de la combinaison suivante: pression ressource, routes ops accessibles sans auth effective, healthchecks trop optimistes, erreurs runtime déjà présentes, et gouvernance multi-repo encore instable.

Le plus urgent n'est pas d'ajouter des features. Il faut d'abord:
1. stabiliser l'hôte et réduire la pression de calcul,
2. remettre une barrière d'auth effective sur `mascarade`,
3. rendre les environnements de test Python reproductibles,
4. figer la vérité Git de `crazy_life` et `Kill_LIFE`,
5. clarifier le contrat de possession entre `mascarade`, `crazy_life` et `Kill_LIFE`.
