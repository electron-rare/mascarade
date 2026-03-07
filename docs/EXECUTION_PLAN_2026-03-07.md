# Plan d'execution - 7 mars 2026

Plan court, factuel, base sur l'etat reel du repo au 7 mars 2026.

## Axe 1 - Cockpit / Observability

### Etat constate
- Le cockpit React et la lane `Logs` sont deja livres.
- La trace inter-agent native avec `run_id` est deja visible dans le cockpit.
- Le lot complementaire `ops-agent + Loki history + OTel exporters` est commence localement mais pas encore valide ni pousse.

### Prochain lot recommande
1. Finaliser `ops-agent` pour les logs machine + Docker live.
2. Stabiliser `api/src/routes/ops.ts` sur `logs/recent`, `logs/query`, `sources`, `summary`.
3. Finir le mode `history` de `web/src/pages/Logs.tsx`.
4. Valider `core`, `api`, `web` et la generation compose.

## Axe 2 - OTel / Loki

### Etat constate
- `loki`, `promtail` et `otel-collector` sont scaffoldes.
- Les exporteurs applicatifs ne sont pas encore relies de bout en bout.

### Prochain lot recommande
1. Brancher les exporteurs OTLP dans le core et l'API.
2. Ajouter les labels utiles cote Loki/Promtail.
3. Rendre l'historique Loki exploitable dans la lane `Logs`.

## Axe 3 - Fine-tuning local

### Etat constate
- Les TODO fine-tuning sont encore valides.
- Le blocage principal reste la validation batch complete jusqu'a `train=completed`.

### Position recommande
1. Garder le fine-tuning en chantier parallele, mais secondaire.
2. Ne pas remelanger ce lot avec l'observability cockpit.

## Axe 4 - Hors scope immediat

- lot CAD / KiCad local
- tuning ClickHouse agressif
- TLS / certificat public

## Ordre global recommande

1. Terminer le lot observability commence localement.
2. Le valider et le pousser proprement.
3. Brancher ensuite OTel + Loki history end-to-end.
4. Revenir seulement apres sur le fine-tuning batch complet.
