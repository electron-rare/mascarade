# Plan d'execution - 7 mars 2026

Plan court, factuel, base sur l'etat reel du repo au 7 mars 2026.

## Axe 1 - Stabilisation locale / hygiene repo

### Etat constate
- Le worktree melange des artefacts frontend, des derives docs `crazy_life`, des choix `finetune` et des notes d'audit.
- Tant que ces sujets restent melanges, les lots TUI/shell deviennent fragiles a integrer proprement.

### Prochain lot recommande
1. Garder un choix CPU coherent dans `finetune`.
2. Isoler `model_selector.py` comme outil experimental.
3. Ranger les remediations MCP dans les sous-modules KiCad.
4. Traiter ensuite seulement les derives docs `crazy_life`.

## Axe 2 - CAD / KiCad

### Etat constate
- Les sous-modules KiCad et les helpers versionnes existent deja.
- Il manque encore le pilotage propre depuis `./config` et `./setup`.

### Etat courant
- La section `CAD / KiCad` dans `./config` est implementee.
- `./setup` supporte `--cad-plugins`, `--cad-doctor`, `--cad-stack`.
- Les helpers plugins/doctor et `cad_stack.sh` sont versionnes.

## Axe 3 - Cockpit / Observability

### Etat constate
- Le cockpit React et la lane `Logs` sont deja livres.
- La trace inter-agent native avec `run_id` est deja visible dans le cockpit.
- Le lot complementaire `ops-agent + Loki history + OTel exporters` est commence localement mais pas encore valide ni pousse.

### Prochain lot recommande
1. Finaliser `ops-agent` pour les logs machine + Docker live.
2. Stabiliser `api/src/routes/ops.ts` sur `logs/recent`, `logs/query`, `sources`, `summary`.
3. Finir le mode `history` de `web/src/pages/Logs.tsx`.
4. Valider `core`, `api`, `web` et la generation compose.

## Axe 4 - OTel / Loki

### Etat constate
- `loki`, `promtail` et `otel-collector` sont scaffoldes.
- Les exporteurs applicatifs ne sont pas encore relies de bout en bout.

### Prochain lot recommande
1. Brancher les exporteurs OTLP dans le core et l'API.
2. Ajouter les labels utiles cote Loki/Promtail.
3. Rendre l'historique Loki exploitable dans la lane `Logs`.

## Axe 5 - Fine-tuning local

### Etat constate
- Les TODO fine-tuning sont encore valides.
- Le blocage principal reste la validation batch complete jusqu'a `train=completed`.

### Position recommande
1. Garder le fine-tuning en chantier parallele, mais secondaire.
2. Ne pas remelanger ce lot avec l'observability cockpit.

## Axe 6 - Hors scope immediat

- tuning ClickHouse agressif
- TLS / certificat public

## Ordre global recommande

1. Stabiliser le lot `finetune` du parent.
2. Ranger les remediations dans les sous-modules KiCad.
3. Traiter ensuite le lot `crazy_life` separement.
4. Reprendre alors le cockpit / observability ou le fine-tuning batch complet.
