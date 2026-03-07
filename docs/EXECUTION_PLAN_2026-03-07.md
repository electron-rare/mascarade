# Plan d'execution - 7 mars 2026

Plan court, factuel, base sur l'etat reel du repo au 7 mars 2026.

## Axe 1 - Stabilisation locale / hygiene repo

### Etat constate
- Le worktree melange des artefacts frontend, des derives docs `crazy_life`, des choix `finetune` et des notes d'audit.
- Tant que ces sujets restent melanges, les lots TUI/shell deviennent fragiles a integrer proprement.

### Prochain lot recommande
1. Nettoyer les artefacts frontend hors lot.
2. Garder un choix CPU coherent dans `finetune`.
3. Isoler les derives docs `crazy_life` dans leur propre lot si elles sont confirmees.
4. Ranger les docs audit dans un commit documentation separe.

## Axe 2 - CAD / KiCad

### Etat constate
- Les sous-modules KiCad et les helpers versionnes existent deja.
- Il manque encore le pilotage propre depuis `./config` et `./setup`.

### Prochain lot recommande
1. Ajouter une section `CAD / KiCad` dans `./config`.
2. Ajouter `--cad-plugins`, `--cad-doctor`, `--cad-stack` dans `./setup`.
3. Consolider la doc operateur CAD.

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

1. Stabiliser le worktree local et ranger les lots non relies.
2. Brancher `CAD / KiCad` dans `config` et `setup`.
3. Terminer ensuite le lot observability commence localement.
4. Brancher apres cela OTel + Loki history end-to-end.
5. Revenir enfin sur le fine-tuning batch complet.
