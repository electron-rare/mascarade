# Local Change Bundles — 2026-03-08

But: figer le residuel local de `mascarade` en lots de commit explicites, apres
stabilisation du contrat multi-repo et remise au propre de `crazy_life` et
`Kill_LIFE`.

## Etat courant

Au moment de ce snapshot:

- `crazy_life` est propre localement
- `Kill_LIFE` est propre localement
- `mascarade` garde `3` lots fonctionnels, puis eventuellement un snapshot frontend

Regle:

- ne pas melanger le lot runtime `Firecrawl` avec le lot `Mem0 + observability`
- ne pas melanger les changements produit/ops avec le snapshot `api/public`
- sortir d'abord les lots fonctionnels
- ne versionner le snapshot frontend qu'en dernier, si vraiment necessaire

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

## Lot 2 — `mem0-observability`

Objet:

- ajouter `Mem0 / OpenMemory` a la stack locale
- exposer cette surface dans `OpsHub` et dans le monitor API
- ajouter le dashboard Grafana `Mascarade Service Logs`
- versionner le rapport de cardinalite Loki et la doc ops associee

Fichiers:

- `.env.example`
- `README.md`
- `TODO_COCKPIT_OPS.md`
- `TODO_VM.md`
- `api/src/routes/ops.ts`
- `deploy/grafana/provisioning/dashboards/json/mascarade-service-logs.json`
- `docker-compose.yml`
- `docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md`
- `docs/RUNBOOK_VM_OPS.md`
- `scripts/compose.sh`
- `scripts/loki_cardinality_report.sh`
- `scripts/modules/mem0.sh`
- `scripts/services.sh`
- `setup`
- `tools/litellm-config.yaml`
- `update`
- `web/src/pages/OpsHub.tsx`

Validation minimale:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'mem0|litellm|qdrant'
ss -lntp | grep 3300
bash scripts/loki_cardinality_report.sh --json >/tmp/loki-cardinality.json || true
cd api && npm run build
cd ../web && npm run build
```

Commit recommande:

```bash
git add .env.example README.md TODO_COCKPIT_OPS.md TODO_VM.md \
  api/src/routes/ops.ts \
  deploy/grafana/provisioning/dashboards/json/mascarade-service-logs.json \
  docker-compose.yml docs/LOCAL_CHANGE_BUNDLES_2026-03-08.md \
  docs/RUNBOOK_VM_OPS.md scripts/compose.sh scripts/loki_cardinality_report.sh \
  scripts/modules/mem0.sh scripts/services.sh setup tools/litellm-config.yaml \
  update web/src/pages/OpsHub.tsx
git commit -m "feat(ops): add mem0 and observability surfaces"
```

## Lot 3 — `mem0-auth-alignment`

Objet:

- aligner les defaults `Mem0` avec `LiteLLM`
- exposer une cle API locale explicite pour `Mem0`
- ajouter l'alias reseau `mem0_store` cote `Qdrant`
- rendre la config `LiteLLM` plus compatible avec les clients OpenAI-compatibles

Fichiers:

- `.env.example`
- `README.md`
- `docker-compose.yml`
- `scripts/compose.sh`
- `scripts/modules/mem0.sh`
- `scripts/modules/qdrant.sh`
- `tools/litellm-config.yaml`

Validation minimale:

```bash
docker compose -f docker-compose.yml config >/tmp/mascarade-compose-check.out
python3 - <<'PY'
import yaml
yaml.safe_load(open('tools/litellm-config.yaml', 'r', encoding='utf-8'))
print('ok')
PY
```

Commit recommande:

```bash
git add .env.example README.md docker-compose.yml scripts/compose.sh \
  scripts/modules/mem0.sh scripts/modules/qdrant.sh tools/litellm-config.yaml
git commit -m "fix(ops): align mem0 auth with litellm runtime"
```

## Lot 4 — `api-public-snapshot` (optionnel)

Objet:

- rafraichir le snapshot frontend servi par `mascarade-api`

Fichiers:

- `api/public/index.html`
- `api/public/assets/*`

Commit recommande:

```bash
git add api/public/index.html api/public/assets
git commit -m "chore(web): refresh api-public snapshot"
```

## Ordre recommande

1. sortir `firecrawl-runtime` dans `mascarade`
2. sortir `mem0-observability` dans `mascarade`
3. sortir `mem0-auth-alignment` si le reliquat reapparait apres commit
4. decider si `api-public-snapshot` doit etre versionne ou laisse hors lot
5. reverifier `git status` dans les trois repos
6. seulement ensuite reprendre un chantier nouveau, pas avant

## Note

Si un nouveau delta reapparait dans `crazy_life` ou `Kill_LIFE`, ne pas le
melanger avec ce lot `mascarade`: il faudra rouvrir un bundle separe par repo.
