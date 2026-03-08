# Remediation Status — 2026-03-08

## Scope
Etat courant apres reprise des RA du re-audit du 7 mars 2026.
Requalification faite sur verifications live du 8 mars 2026 (`free -h`, `ss`, `docker ps`, `ops-agent`, `/api/ops/summary`, et etat Git local des repos).
Checks canoniques rejoues et valides le 8 mars 2026:

- `mascarade`: `scripts/test_python.sh --bootstrap`, build `api`, build `web`, `docker compose config -q`, `/api/ops/summary`
- `Kill_LIFE`: `tools/test_python.sh --suite stable`, `mcp_runtime_status.py --json`, smokes `knowledge-base`, `github-dispatch`, `nexar_api`
- `crazy_life`: build `web`, `scripts/publish_preflight.sh check`

Backlog de reference:
- `REMEDIATION_BACKLOG_2026-03-07_REAUDIT.md`

## Global status
- Remediations verifiees comme fermees: `RA-001` a `RA-013`
- Gate RA actif: aucun
- Restes specialises hors ligne `RA-*`: aucun blocker MCP/agentics local actif; `K-012` devient optionnel tant que le runtime conteneur KiCad reste canonique; `nexar_api` est valide en live mais limite par un quota Nexar externe sur le token de reference
- Follow-up post-`RA-*` actif dans `mascarade`: `operator-surfaces-public-proxy`
  - statut: local implemente et verifie, en attente de publication
  - perimetre: surfaces operateur publiques avec auth via `edge-proxy`, `api` runtime `Kill_LIFE` en `rw`, `OpsHub` recale sur les URLs proxifiees

## Detail par RA

### RA-001 — Serialiser le fine-tuning CPU
- Status: **Done**
- Etat:
  - les lanes CPU paralleles ont ete ramenes sous controle;
  - la machine n'est plus en pression critique;
  - regle de cloture retenue: ignorer le swap tant qu'il reste sous `33%` de la RAM machine ou qu'il est en cours de purge naturelle.

### RA-002 — Reactiver une auth runtime reelle sur `mascarade`
- Status: **Done**
- Outcome:
  - `MASCARADE_API_KEY` est traitee comme exigence de securite runtime;
  - l'API, le core et l'ops-agent restent proteges par token.

### RA-003 — Reduire la surface hote exposee
- Status: **Done**
- Outcome:
  - la reduction de surface initiale a bien ete appliquee pendant la phase de stabilisation;
  - la publication publique actuelle des surfaces operateur se traite maintenant dans le follow-up `operator-surfaces-public-proxy`, avec auth dediee et hostnames `*.saillant.cc`, sans rouvrir `RA-003`.

### RA-004 — Reparer le contrat `ops-agent` / `summary` / GPU
- Status: **Done**
- Outcome:
  - le GPU remonte de facon coherente dans `ops-agent`, `sources` et `summary`.

### RA-005 — Stabiliser le pipeline logs/history
- Status: **Done**
- Outcome:
  - le stream live est borne;
  - le bruit nominal `promtail/loki` n'est plus traite comme signal bloquant;
  - le faux signal `openwebui` a disparu apres redeploiement du runtime API aligne sur le source courant.

### RA-006 — Corriger la publication distante reelle de `crazy_life`
- Status: **Done**
- Outcome:
  - le preflight remote GitHub prive est corrige;
  - le chemin canonique de publication reste `crazy_life/main`;
  - les deltas locaux restants relevent maintenant de la consolidation/publish, plus de cette remediation.

### RA-007 — Geler une commande bootstrap/test Python par repo
- Status: **Done**
- Outcome:
  - `mascarade` et `Kill_LIFE` ont chacun un chemin bootstrap/test documente et executable.

### RA-008 — Rendre `mascarade/web` non salissant
- Status: **Done**
- Outcome:
  - le chemin `build:api-public` existe bien pour rafraichir explicitement les artefacts servis;
  - le build par defaut n'encrasse plus le worktree suivi;
  - les artefacts servis ne sont plus generes implicitement.

### RA-009 — Reduire la derive locale de `Kill_LIFE`
- Status: **Done**
- Outcome:
  - des supports de revue et de bundling existent localement;
  - la derive est maintenant lisible et publiable par sujet.

### RA-010 — Requalifier la matrice secrets
- Status: **Done**
- Outcome:
  - la source de verite runtime-secrets et provider-status distingue bien `Mascarade auth`, `Knowledge Base MCP`, `GitHub dispatch MCP`, `HuggingFace MCP` et les providers LLM;
  - `MASCARADE_API_KEY` n'est plus noyee dans les providers optionnels;
  - la page Settings distingue la securite runtime des integrations runtime et des providers;
  - le MCP `knowledge-base` est valide en live sur le provider actif `memos`;
  - `GitHub dispatch MCP` est valide en live via token persiste;
  - le MCP `HuggingFace` est a nouveau `ready` en mode remote HTTP anonyme;
  - les restes specialises restants ne relevent plus de cette remediation; `K-012` devient optionnel tant que le runtime conteneur KiCad reste canonique, et `nexar_api` est valide en live avec une limite de quota Nexar externe qui ne rouvre pas le gate `RA-*`.

### RA-011 — Clarifier le contrat multi-repo
- Status: **Done**
- Outcome:
  - le contrat est aligne dans plusieurs docs locales sur la meme phrase:
    - `crazy_life` = repo canonique web/devops;
    - `Kill_LIFE` = source de verite runtime/workflows/evidence;
    - `mascarade` = repo compagnon/orchestration + bridge optionnel.
  - les deltas locaux restants relevent de la publication par bundles, pas d'une ambiguite de contrat.

### RA-012 — Renforcer CI et release autour des chemins canoniques reels
- Status: **Done**
- Outcome:
  - `crazy_life` porte bien des changements locaux pour couvrir API tests, API build et web build, et pour publier `api/public`;
  - `Kill_LIFE` porte un nouveau `ci.yml` coherent avec le chemin repo-local stable;
  - les chemins canoniques sont clarifies; le reste est une phase normale de publication locale/distante.

### RA-013 — Differer les validations E2E non critiques jusqu'a stabilisation
- Status: **Done**
- Outcome:
  - le gate de report est explicite dans l'etat d'audit;
  - `batch fine-tuning completed` et `n8n import E2E` restent differees hors gate critique.

## Gate E2E

Ne pas rouvrir comme gates critiques:
- batch fine-tuning completed
- n8n import E2E

Condition de reouverture:
1. besoin explicite de validation E2E;
2. bundles locaux consolides sur les repos concernes.

## Next step
1. Le backlog `RA-*` reste clos; ne pas le rouvrir sans signal reel de regression.
2. Publier le follow-up `operator-surfaces-public-proxy` dans `mascarade`.
3. Aucun chantier repo-suivi local n'est actif sur la ligne `MCP/agentics`.
4. Garder les sujets encore ouverts hors audit:
   - secrets providers optionnels si un provider supplementaire doit etre actif;
   - setup Mac local (`MCP`, `Playwright MCP`) si ce poste doit redevenir un environnement operateur.
5. N'ouvrir un chantier Nexar supplementaire que si le sourcing live requiert un token/plan avec quota de parts non nul.
6. Ne rejouer `K-012` que si le host-native KiCad devient une exigence runtime.
