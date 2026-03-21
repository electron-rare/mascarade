# Publication Matrix Inter-Repos (2026-03-15)

## Goal

Define a single publication contract across the active repositories:
- who publishes what
- from which branch
- with which prechecks
- with which dependency order

## Matrix

| Repo | Publishable output | Canonical branch | Local prechecks | CI gate | Depends on |
| --- | --- | --- | --- | --- | --- |
| crazy_life | frontend build artifact in api/public, API gateway build | main | npm run release:check | ci.yml + deploy-pages.yml | none |
| Kill_LIFE | evidence packs, compliance artifacts, signed release outputs | main | python tools/validate_specs.py + python tools/compliance/validate.py --strict | workflow gates in .github/workflows | none |
| mascarade-main | runtime images, core/api readiness, operator stack state | main | bash scripts/test_python.sh, npm --prefix api run build, docker compose config | repo CI + merge lots gates | Kill_LIFE evidence, crazy_life release readiness |
| mascarade | companion runtime and sync bridge state | feat/apple-coreml-runtime-lot (current), target main alignment | scripts/sync_crazy_life.sh status + local runtime checks | repo CI | mascarade-main trunk policies |

## Dependency order for release windows

1. Kill_LIFE prechecks and artifacts are green
2. crazy_life release preflight is green
3. mascarade-main publication gates are green
4. mascarade companion alignment checks are green

## Standard gate commands

### crazy_life

```bash
cd /Users/electron/crazy_life
npm run release:status
npm run release:check
npm run release:probe-remote
```

### Kill_LIFE

```bash
cd /Users/electron/Kill_LIFE
python3 tools/validate_specs.py
python3 tools/compliance/validate.py --strict
```

### mascarade-main

```bash
cd /Users/electron/mascarade-main
bash scripts/merge_preflight.sh baseline
bash scripts/test_python.sh -- -q
npm --prefix api run build
docker compose config >/dev/null
```

## Automation roadmap

### Wave 1 (local unified gate)

Add one wrapper command in mascarade-main:
- run all local prechecks in dependency order
- fail fast with clear output

Target script:
- scripts/pre_publication_gate.sh

### Wave 2 (registry and artifact promotion)

- add image publication for mascarade-main
- attach digest/SBOM/provenance metadata
- keep promotion conditional on Wave 1 success

### Wave 3 (orchestrated inter-repo release)

- orchestrate release order and rollback strategy
- track each repo gate status in one report artifact

## Audit trail requirements

Each publication run should persist:
- timestamp
- branch + commit for each repo
- executed checks and exit status
- generated artifacts references

Recommended location:
- docs/audit/
