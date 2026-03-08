# Local Change Bundles — 2026-03-08

But: figer le residuel local de `mascarade` en lots de commit explicites, apres
stabilisation du contrat multi-repo et remise au propre de `crazy_life` et
`Kill_LIFE`.

## Etat courant

Au moment de ce snapshot:

- `crazy_life` est propre localement
- `Kill_LIFE` est propre localement
- `mascarade` garde `1` lot principal et `1` lot optionnel

Regle:

- ne pas melanger le lot runtime `Firecrawl` avec l'ajout du dashboard Grafana
- sortir d'abord le lot runtime
- ne sortir le dashboard que si tu veux vraiment versionner cette nouvelle vue ops

## Lot 1 — `firecrawl-runtime`

Objet:

- exposer `FIRECRAWL_HOST` comme variable runtime explicite
- corriger le bind/healthcheck du service `firecrawl`
- aligner la doc runtime et les TODO VM sur l'etat reel de la stack

Fichiers:

- `.env.example`
- `README.md`
- `TODO_VM.md`
- `docker-compose.yml`
- `docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md`
- `docs/EXECUTION_PLAN_2026-03-07.md`
- `docs/audit/AUDIT_COMPLET_2026-03-07.md`
- `scripts/compose.sh`
- `scripts/modules/firecrawl.sh`

Revue:

```bash
git diff -- .env.example README.md TODO_VM.md docker-compose.yml \
  docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md docs/EXECUTION_PLAN_2026-03-07.md \
  docs/audit/AUDIT_COMPLET_2026-03-07.md scripts/compose.sh \
  scripts/modules/firecrawl.sh
```

Validation minimale:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep firecrawl
ss -lntp | grep 3400
```

Commit recommande:

```bash
git add .env.example README.md TODO_VM.md docker-compose.yml \
  docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md docs/EXECUTION_PLAN_2026-03-07.md \
  docs/audit/AUDIT_COMPLET_2026-03-07.md scripts/compose.sh \
  scripts/modules/firecrawl.sh
git commit -m "feat(ops): stabilize firecrawl runtime in local stack"
```

## Lot 2 — `grafana-service-logs` (optionnel)

Objet:

- ajouter un dashboard Grafana dedie aux logs de services `mascarade`

Fichiers:

- `deploy/grafana/provisioning/dashboards/json/mascarade-service-logs.json`

Revue:

```bash
jq -r '.title, .uid' deploy/grafana/provisioning/dashboards/json/mascarade-service-logs.json
jq empty deploy/grafana/provisioning/dashboards/json/mascarade-service-logs.json
```

Commit recommande:

```bash
git add deploy/grafana/provisioning/dashboards/json/mascarade-service-logs.json
git commit -m "feat(grafana): add service logs dashboard"
```

## Ordre recommande

1. sortir `firecrawl-runtime` dans `mascarade`
2. decider si `grafana-service-logs` doit etre versionne ou laisse hors lot
3. reverifier `git status` dans les trois repos
4. seulement ensuite reprendre un chantier nouveau, pas avant

## Note

Si un nouveau delta reapparait dans `crazy_life` ou `Kill_LIFE`, ne pas le
melanger avec ce lot `mascarade`: il faudra rouvrir un bundle separe par repo.
