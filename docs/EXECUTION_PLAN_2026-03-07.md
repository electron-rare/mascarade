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

### Etat courant (verifie par audit 7 mars)
- Les sous-modules KiCad pointent vers electron-rare (commite).
- La section `CAD / KiCad` dans `./config` est implementee.
- `./setup` supporte `--cad-plugins`, `--cad-doctor`, `--cad-stack`.
- Les helpers plugins/doctor et `cad_stack.sh` sont versionnes.
- Reste: smoke TUI, doc chemins par OS, doctor MCP dedie.

## Axe 3 - Cockpit / Observability

### Etat courant (verifie par audit 7 mars)
- Le cockpit React et la lane `Logs` sont livres.
- `ops-agent` est **complet**: /health, /sources, /summary, /logs/recent, /logs/stream (SSE).
- `api/src/routes/ops.ts` est **stable**: logs/recent, logs/query (Loki), logs/stream, summary (avec MCP probe).
- Le mode `history` de `web/src/pages/Logs.tsx` est **implemente**: toggle live/history, fenetres 15m/1h/6h/24h, recherche texte.
- Exporteurs OTel custom implementes dans core (`otel.py`) et API (`otel.ts`).

### Prochain lot recommande
1. Configurer un vrai exporter dans `deploy/otel-collector/config.yaml` (actuellement stub debug-only).
2. Configurer Grafana datasources (Loki + Prometheus) en code.
3. Ajouter un probe GPU (nvidia-smi) dans ops-agent ou API.

## Axe 4 - OTel / Loki

### Etat courant (verifie par audit 7 mars)
- `loki`, `promtail` et `otel-collector` deployes dans docker-compose.
- Exporteurs OTLP custom branches dans core et API (OTEL_ENABLED=true).
- **OTel Collector** recoit les donnees mais exporte uniquement en debug (stdout).
- Promtail scrape Docker + journald vers Loki.

### Prochain lot recommande
1. Remplacer l'exporter debug du Collector par un vrai backend (Loki, Jaeger, etc.).
2. Enrichir Promtail pour parser les logs JSON structures.
3. Verifier les labels Loki utiles: `source`, `run_id`, `agent_name`, `event_type`, `severity`.

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
