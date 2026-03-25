# Phase 2 Stack

This folder carries the secondary local stack for:

- `SearXNG`
- `Paperless-ngx`
- `Karakeep`

Defaults are intentionally local-first:

- host ports bind to `127.0.0.1`
- operator access should go through `edge-proxy`
- secrets stay in `deploy/phase2/.env`, not in Git

Bootstrap:

```bash
cd /home/clems/mascarade/deploy/phase2
cp .env.example .env
docker compose --env-file .env -f docker-compose.yml up -d
```

Expected operator hostnames behind the main proxy:

- `search.saillant.cc`
- `paperless.saillant.cc`
- `karakeep.saillant.cc`

<iframe src="https://github.com/sponsors/electron-rare/card" title="Sponsor electron-rare" height="225" width="600" style="border: 0;"></iframe>
