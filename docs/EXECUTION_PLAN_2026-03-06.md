# Plan d'execution - 6 mars 2026

Statut suite:
- type: `historical-reference`
- source active: `docs/EXECUTION_HUB.md`
- regle: plan archive, a ne pas utiliser comme backlog actif

Plan court, factuel, base sur l'etat actuel du repo et des derniers runs locaux.

## Axe 1 - Fine-tuning local

### Etat constate
- Le bug `esp32 -> iot` au merge n'est plus le probleme actif.
- Les derniers manifests batch montrent `distill=completed` pour `esp32`, `spice`, `pio`.
- La validation end-to-end reste incomplete car les runs s'arretent avec `train=pending`.

### Prochain lot recommande
1. Reprendre un run batch existant avec `--resume` jusqu'a fin de `train`.
2. Suivre les manifests avec `python3 finetune/batch_status.py`.
3. Mesurer ensuite le mode `gpu_slots=2`.

## Axe 2 - Stack runtime

### Etat constate
- Le reverse proxy `edge-proxy` est en place.
- Seuls `80/443` sont publics quand `PUBLISH_BIND_HOST=127.0.0.1`.
- Le lot certificat est volontairement mis en pause.

### Prochain lot recommande
1. Garder le proxy comme mode de reference.
2. Traiter TLS plus tard, separement.
3. Ne pas melanger ce lot avec la stabilisation fine-tuning.

## Axe 3 - Frontend et ops

### Etat constate
- Le cockpit frontend et `ops-console` coexistent encore.
- Le point d'entree public unique existe deja via `edge-proxy`.

### Prochain lot recommande
1. Decider si `ops-console` reste une landing page ou s'il est absorbe.
2. Eviter de maintenir deux experiences concurrentes plus longtemps.
3. Prioriser les pages les plus operations: dashboard, metrics, health.

## Ordre global recommande

1. Stabiliser le batch local jusqu'a `train=completed`.
2. Ajouter un resume de statut batch exploitable.
3. Revenir ensuite sur l'unification frontend / ops-console.
4. Reprendre TLS seulement apres ces lots.
