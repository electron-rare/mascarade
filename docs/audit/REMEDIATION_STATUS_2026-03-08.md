# Remediation Status — 2026-03-08

## Scope
Etat courant apres reprise des RA du re-audit du 7 mars 2026.
Requalification faite sur verifications live du 8 mars 2026 (`free -h`, `ss`, `docker ps`, `ops-agent`, `/api/ops/summary`, et etat Git local des repos).

Backlog de reference:
- `REMEDIATION_BACKLOG_2026-03-07_REAUDIT.md`

## Global status
- Remediations verifiees comme fermees: `RA-002`, `RA-003`, `RA-004`, `RA-005`, `RA-007`, `RA-013`
- Remediations encore partielles: `RA-001`, `RA-006`, `RA-008`, `RA-009`, `RA-010`, `RA-011`, `RA-012`
- Point de gate actif: la machine n'est plus sous pression critique; le cockpit est redevenu propre, mais l'agregat MCP reste `degraded` tant que `Notion` et `GitHub dispatch` ne sont pas valides en live

## Detail par RA

### RA-001 — Serialiser le fine-tuning CPU
- Status: **Partial**
- Etat:
  - les lanes CPU paralleles ont ete ramenes sous controle;
  - la machine n'est plus en pression critique;
  - le sujet reste ouvert tant que le swap n'est pas revenu a un niveau de repos durable.

### RA-002 — Reactiver une auth runtime reelle sur `mascarade`
- Status: **Done**
- Outcome:
  - `MASCARADE_API_KEY` est traitee comme exigence de securite runtime;
  - l'API, le core et l'ops-agent restent proteges par token.

### RA-003 — Reduire la surface hote exposee
- Status: **Done**
- Outcome:
  - la publication `80/443` de la pile `mascarade` reste bornee au loopback;
  - le bridge n'est plus considere comme une justification de release publique.

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
- Status: **Partial**
- Outcome:
  - les changements locaux existent bien dans `crazy_life` pour la CI, Pages et le preflight remote;
  - le chemin canonique de publication reste `crazy_life/main`;
  - la correction reste partielle tant que le repo `crazy_life` est encore sale localement et que la publication distante n'a pas ete reverifiee end-to-end.

### RA-007 — Geler une commande bootstrap/test Python par repo
- Status: **Done**
- Outcome:
  - `mascarade` et `Kill_LIFE` ont chacun un chemin bootstrap/test documente et executable.

### RA-008 — Rendre `mascarade/web` non salissant
- Status: **Partial**
- Outcome:
  - le chemin `build:api-public` existe bien pour rafraichir explicitement les artefacts servis;
  - le chantier n'est pas ferme: le worktree `mascarade` reste encore sali par `api/public/index.html` et `api/public/assets/*`.

### RA-009 — Reduire la derive locale de `Kill_LIFE`
- Status: **Partial**
- Outcome:
  - des supports de revue par lots existent localement;
  - la derive reste importante: `Kill_LIFE` garde un gros delta local, des fichiers non suivis et des changements encore non consolides.

### RA-010 — Requalifier la matrice secrets
- Status: **Partial**
- Outcome:
  - la source de verite runtime-secrets et provider-status distingue bien `Mascarade auth`, `Notion MCP`, `GitHub dispatch MCP`, `HuggingFace MCP` et les providers LLM;
  - `MASCARADE_API_KEY` n'est plus noyee dans les providers optionnels;
  - la page Settings distingue la securite runtime des integrations runtime et des providers;
  - le MCP `HuggingFace` est a nouveau `ready` en mode remote HTTP anonyme;
  - le runtime reste degrade tant que `NOTION_*` et `GITHUB_*` ne sont pas valides en live.

### RA-011 — Clarifier le contrat multi-repo
- Status: **Partial**
- Outcome:
  - le contrat est aligne dans plusieurs docs locales sur la meme phrase:
    - `crazy_life` = repo canonique web/devops;
    - `Kill_LIFE` = source de verite runtime/workflows/evidence;
    - `mascarade` = repo compagnon/orchestration + bridge optionnel.
  - le chantier reste partiel tant que les trois repos gardent des deltas locaux importants et des documents de statut divergents.

### RA-012 — Renforcer CI et release autour des chemins canoniques reels
- Status: **Partial**
- Outcome:
  - `crazy_life` porte bien des changements locaux pour couvrir API tests, API build et web build, et pour publier `api/public`;
  - `Kill_LIFE` porte un nouveau `ci.yml` coherent avec le chemin repo-local stable;
  - le chantier reste partiel tant que ces changements ne sont pas stabilises dans les worktrees et reverifies comme chemin canonique de publication/release.

### RA-013 — Differer les validations E2E non critiques jusqu'a stabilisation
- Status: **Done**
- Outcome:
  - le gate de report est explicite dans l'etat d'audit;
  - `batch fine-tuning completed` et `n8n import E2E` restent differees hors gate critique.

## Gate E2E actif

Ne pas rouvrir comme gates critiques:
- batch fine-tuning completed
- n8n import E2E

Condition de reouverture:
1. machine revenue a un etat de repos stable (`RA-001`);
2. matrice secrets, contrat multi-repo et CI/release gardes coherents.

## Next step
1. Terminer `RA-001` en verifiant le retour durable a un niveau de swap de repos acceptable.
2. Fermer `RA-010` en remettant l'agregat MCP au vert:
   - renseigner et valider `Notion`;
   - renseigner et valider `GitHub dispatch`;
3. Requalifier ensuite `RA-008`, `RA-009` et `RA-012` une fois les worktrees vraiment assainis.
