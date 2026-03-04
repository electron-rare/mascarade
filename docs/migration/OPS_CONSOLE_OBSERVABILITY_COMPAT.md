# Ops Console Observability Compatibility (V2/V3)

Contexte: certaines machines surveillent encore `zacus-ops-console` alors que la cible est `ops-console-v3`.  
Pour eviter les faux positifs pendant migration, on utilise un alias logique `ops-console` qui accepte:
- `ops-console-v3` (V3),
- ou `zacus-ops-console` (V2 legacy).

## Script d'application

```bash
bash scripts/apply_ops_console_observability_compat.sh
```

Le script met a jour:
- `/opt/docker-studio-ai/tools/dev/docker-studio-ai/scripts/container_observability_check.sh`
- `/opt/docker-studio-ai/tools/dev/docker-studio-ai/scripts/healthcheck.sh`
- `/opt/docker-studio-ai/tools/dev/docker-studio-ai/.env.local`

Puis recharge/restart:
- `container-observability.timer`
- `container-observability.service`

## Verification

```bash
systemctl status container-observability.timer --no-pager
systemctl status container-observability.service --no-pager
tail -n 50 /var/log/container-observability-alerts.log
```

Attendu:
- plus d'alertes `name=zacus-ops-console state=missing`,
- presence d'un etat `name=ops-console state=healthy` si V2 ou V3 tourne.
