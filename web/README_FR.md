# Crazy Life

Bridge workspace for the standalone `crazy_life` repo.

This directory is no longer the canonical home of the cockpit. The canonical frontend+backend target is `crazy_life`; `mascarade/web` is kept as a subtree bridge when sync is still needed.

## Run

```bash
npm install
npm run dev
```

The dev server proxies `/api` and `/health` to `http://localhost:3100`.

When you run the extracted repo against the local Mascarade API dev server, the default proxy target is:

```bash
http://localhost:3000
```

When you want to target the Docker/API runtime on `3100` instead:

```bash
CRAZY_LIFE_API_ORIGIN=http://localhost:3100 npm run dev
```

## Build

```bash
npm run build
```

Default build artifacts are emitted to `dist/` and should not modify tracked files in `mascarade`.

When you intentionally want to refresh the versioned bridge snapshot served by `mascarade-api`, use:

```bash
npm run build:api-public
```

Policy:

- `dist/` = local build artifact, ignored
- `api/public/` = explicit bridge snapshot, refreshed only on purpose
- `node_modules/.cache/tsconfig.tsbuildinfo` = local TypeScript cache, ignored via `node_modules/`

## Local Deploy

Docker deployment is available for the extracted repo and for `mascarade/web`:

```bash
scripts/deploy_local.sh up
```

Default local URL:

```text
http://127.0.0.1:8088
```

Default upstreams:

```text
CRAZY_LIFE_API_ORIGIN=http://host.docker.internal
CRAZY_LIFE_PROXY_ORIGIN=http://host.docker.internal
```

That means:

- `/api` and `/health` go through the main Mascarade reverse proxy on `80/443`
- `/core-health` and `/dify-health` go through the main reverse-proxy host

Useful commands:

```bash
scripts/deploy_local.sh build
scripts/deploy_local.sh up
scripts/deploy_local.sh logs
scripts/deploy_local.sh down
```

## GitHub Pages

The extracted repository ships GitHub Actions workflows for:

- `ci.yml`: install + build on push and pull request
- `deploy-pages.yml`: build and deploy `main` to GitHub Pages

The Pages workflow sets:

```bash
CRAZY_LIFE_BASE=/crazy_life/
```

so the router and static assets work under the repository path.

## Sync Flow

Inside `mascarade`:

```bash
scripts/sync_crazy_life.sh init-remote
scripts/sync_crazy_life.sh push --allow-dirty --force
scripts/sync_crazy_life.sh pull
```

Rules:

- run the canonical release preflight in the extracted `crazy_life` repo before any publish attempt
- `push` exports the committed `web/` subtree to `crazy_life`; release readiness is still decided in the extracted repo
- `pull` fetches `crazy_life/main`, replaces `web/` from that tree and creates a local sync commit
- `pull` requires a clean worktree
- `push --allow-dirty` is safe for local unrelated changes because only `HEAD:web` is exported
- product ownership lives in `crazy_life`, not in `mascarade/web`

<iframe src="https://github.com/sponsors/electron-rare/card" title="Sponsor electron-rare" height="225" width="600" style="border: 0;"></iframe>
