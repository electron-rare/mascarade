# Registry-First MCP Review - 2026-03-14

## Scope

This pass converts the 2026 web notes and local MCP wiring into a durable registry-first map for `mascarade`.

Primary anchors used in this repo:

- local runtime/client wiring in `core/mascarade/mcp/client.py`
- ops probing in `api/src/routes/ops.ts` and `deploy/ops_agent/app.py`
- optional MCP service wiring in `scripts/modules/firecrawl.sh`, `scripts/modules/mem0.sh`, and `README.md`
- local Codex MCP config at `~/.codex/config.toml`
- versioned inventory at `scripts/data/mcp_registry_inventory.json`

Reference memories used for this lot:

- `/Users/electron/.codex/memories/electron_rare_chantier/MANIFEST_EASTER_EGGS_REF_2026-03-11.md`
- `/Users/electron/.codex/memories/electron_rare_chantier/WEB_NOTES_2026-03-13_GATEWAY_MCP.md`
- `/Users/electron/.codex/memories/electron_rare_chantier/WEB_2026_TO_BACKLOG_2026-03-14.md`

Official source links checked during this pass:

- Notion developer setup for Codex: https://developers.notion.com/docs/get-started-with-mcp
- GitHub MCP registry page for Notion: https://github.com/mcp/makenotion/notion-mcp-server
- Hugging Face MCP docs: https://huggingface.co/docs/hub/en/hf-mcp-server
- GitHub MCP registry page for Hugging Face: https://github.com/mcp/huggingface/hf-mcp-server
- GitHub MCP registry page for Playwright: https://github.com/mcp/microsoft/playwright-mcp
- Firecrawl MCP docs: https://docs.firecrawl.dev/mcp-server
- GitHub MCP registry page for Firecrawl: https://github.com/mcp/firecrawl/firecrawl-mcp-server
- Mem0 OpenMemory overview: https://docs.mem0.ai/openmemory/overview
- Mem0 MCP docs: https://docs.mem0.ai/platform/mem0-mcp
- Public community KiCad server upstream: https://github.com/mixelpixx/KiCAD-MCP-Server
- GitHub MCP registry overview: https://github.com/mcp

## Classification Rules

- `official`: vendor-maintained or curated official package/server
- `community-valid`: public community upstream exists and is maintainable, but it is not the canonical official connector here
- `local-only`: custom launcher or sibling-repo runtime without a public registry target for this workspace

`registry_status` stays separate from the class:

- `curated-registry`: seen in the curated MCP registry/GitHub registry during this pass
- `vendor-official-upstream`: official vendor source confirmed, but no curated-registry hit was captured in this pass
- `not-found-in-curated-registry-snapshot`: no curated-registry hit captured in this pass
- `local-custom`: sibling-repo or private runtime

## Durable Findings

### Local Codex config

The current local Codex MCP config contains:

- `notion`
- `kicad`
- `validate-specs`
- `knowledge-base`
- `github-dispatch`
- `freecad`
- `openscad`
- `huggingface`
- `playwright`

Important drift found on the actual local config:

- `kicad`, `knowledge-base`, `github-dispatch`, `freecad`, and `openscad` still set `MASCARADE_DIR=/Users/electron/mascarade-main`
- `validate-specs`, `freecad`, and `openscad` still omit explicit `startup_timeout_sec`
- Codex session logs on `2026-03-11` and `2026-03-14` show `validate-specs`, `freecad`, and `openscad` timing out after the default `10s`
- `kicad`, `knowledge-base`, and `github-dispatch` fail earlier with a closed `initialize` response, so this follow-up does not hide that handshake class behind larger timeouts
- direct write to `~/.codex/config.toml` was blocked in this sandbox (`PermissionError: [Errno 1] Operation not permitted`), so the repo validated a corrected shadow config instead of claiming a write that did not happen

Review execution captured in this follow-up:

- actual command: `./scripts/tui/mcp_registry_review.sh audit --config "$HOME/.codex/config.toml" --ops-dir .ops/registry-first/actual --yes`
- actual summary: `18` inventory servers, `9` configured, `3` aligned, `6` drift, `9` absent
- shadow command: `./scripts/tui/mcp_registry_review.sh audit --config /tmp/mascarade-mcp-local-shadow.toml --ops-dir .ops/registry-first/shadow --yes`
- shadow summary: `18` inventory servers, `9` configured, `9` aligned, `0` drift, `9` absent
- validated shadow values: `MASCARADE_DIR=/Users/electron/mascarade` for `kicad`, `knowledge-base`, `github-dispatch`, `freecad`, `openscad`; `startup_timeout_sec=20` for `validate-specs`; `startup_timeout_sec=30` for `openscad`; `startup_timeout_sec=45` for `freecad`

### Registry-first matrix

| Server | Current local integration | Class | Registry status | Local config state | Decision |
| --- | --- | --- | --- | --- | --- |
| `notion` | remote Codex entry -> `https://mcp.notion.com/mcp` | `official` | `curated-registry` | present, aligned | keep remote official endpoint; do not regress to local custom Notion MCP |
| `huggingface` | remote Codex entry + ops-agent remote probe | `official` | `curated-registry` | present, aligned | keep remote official endpoint |
| `playwright` | local Codex entry -> `npx @playwright/mcp@latest` | `official` | `curated-registry` | present, aligned | keep official package path |
| `firecrawl` | repo optional service via `mcp/firecrawl` | `official` | `curated-registry` | absent from Codex config | optional add later only if an MCP client needs direct access; repo service wiring is already official |
| `mem0` | repo optional service via `mem0/openmemory-mcp` | `official` | `vendor-official-upstream` | absent from Codex config | keep as optional upstream official service; do not label it curated-registry yet without a hit |
| `kicad` | local launcher -> `Kill_LIFE/tools/hw/run_kicad_mcp.sh` -> vendored server in `finetune/kicad_mcp_server` | `community-valid` | `not-found-in-curated-registry-snapshot` | present, drift on `MASCARADE_DIR` in actual config; aligned in shadow config | keep as explicit community-valid local runtime, not as an official registry server |
| `validate-specs` | local launcher in `Kill_LIFE` | `local-only` | `local-custom` | present, missing `startup_timeout_sec` in actual config; aligned in shadow config with `20s` | keep local-only |
| `knowledge-base` | local launcher in `Kill_LIFE` + mascarade integration | `local-only` | `local-custom` | present, drift on `MASCARADE_DIR` | keep local-only |
| `github-dispatch` | local launcher in `Kill_LIFE` + mascarade integration | `local-only` | `local-custom` | present, drift on `MASCARADE_DIR` | keep local-only |
| `freecad` | local launcher in `Kill_LIFE` | `local-only` | `local-custom` | present, drift on `MASCARADE_DIR` + missing `startup_timeout_sec` in actual config; aligned in shadow config with `45s` | keep local-only |
| `openscad` | local launcher in `Kill_LIFE` | `local-only` | `local-custom` | present, drift on `MASCARADE_DIR` + missing `startup_timeout_sec` in actual config; aligned in shadow config with `30s` | keep local-only |
| `cockpit-ops`, `plm`, `qms`, `mes`, `erp`, `wms`, `dcs` | conditional sibling-repo runtimes from `agent-factory-cockpit` | `local-only` | `local-custom` | not in Codex config | keep local-only and document as conditional |

## Decisions Absorbed

1. `mascarade` now has a versioned inventory for registry-first MCP review instead of relying on free-form notes.
2. Remote official connectors stay first-class for `notion`, `huggingface`, and `playwright`.
3. `firecrawl` and `mem0` stay documented as official optional services owned by upstream vendors, but they are not auto-added to local Codex config in this lot.
4. CAD and industrial launchers stay explicit about their status:
   - `kicad` = community-valid local runtime
   - `validate-specs`, `knowledge-base`, `github-dispatch`, `freecad`, `openscad`, `cockpit-ops`, `plm`, `qms`, `mes`, `erp`, `wms`, `dcs` = local-only
5. The local review contract now checks both `MASCARADE_DIR` drift and minimum `startup_timeout_sec` for slow local launchers.
6. Direct mutation of `~/.codex/config.toml` stayed blocked by sandbox in this lot; the corrected shadow config was still validated to `9 aligned / 0 drift / 9 absent`.

## Tooling Added

- `scripts/data/mcp_registry_inventory.json`
  - durable inventory for registry-first MCP classes and expected config targets
- `scripts/tui/mcp_registry_review.sh`
  - Bash review CLI/TUI with:
    - `run|audit|purge-raw|purge`
    - auto-detection of common MCP config files
    - Codex TOML parsing plus JSON MCP config fallback
    - drift checks against expected command/url targets
    - minimum startup-timeout checks for local slow launchers (`validate-specs>=20`, `openscad>=30`, `freecad>=45`)
    - raw artifact generation under `.ops/registry-first/`
    - raw artifact purge while keeping `report.md`

Recommended operator call:

```bash
./scripts/tui/mcp_registry_review.sh run --config "$HOME/.codex/config.toml" --purge-raw --yes
```

## Logs and Purge

This lot followed the `generate -> analyze -> purge` rule from the manifest reference:

1. generate raw review artifacts in `.ops/registry-first/`
2. extract durable conclusions into this document and the TODO/plan updates
3. purge raw artifacts after extraction

Final state expected after the lot:

- `.ops/registry-first/actual/report.md` and `.ops/registry-first/shadow/report.md` may remain temporarily if the operator wants local scratch reports
- raw `.log`, `.json`, `.tsv` artifacts in those directories must be removed
- the temporary `/tmp/mascarade-mcp-local-shadow.toml` must be removed after extraction
- this follow-up purged the raw artifacts and removed the temporary shadow config

## Remaining Backlog

- decide whether `firecrawl` should be added to local Codex MCP config on this machine or stay repo-only
- decide whether `mem0` should be exposed to a local MCP client on this machine or stay repo-only
- apply the validated shadow config onto `~/.codex/config.toml` from a context that can write outside the workspace sandbox
- keep future additions registry-first by updating `scripts/data/mcp_registry_inventory.json` before editing local config docs
