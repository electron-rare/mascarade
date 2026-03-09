# Next Useful Lot State

Generated: 2026-03-09 06:06:29 CET

## Summary

- Detected lot: `kill-life-followup`
- Kind: `local`
- Primary repo: `Kill_LIFE`
- Primary root: `/home/clems/Kill_LIFE`
- Reason: Tracked local changes remain in Kill_LIFE and should be checked with the stable Python/spec suite.

## Repo Snapshot

- `mascarade`: 0 tracked delta(s)
- `crazy_life`: 0 tracked delta(s)
- `Kill_LIFE`: 10 tracked delta(s)
- `agent-factory-cockpit`: 0 tracked delta(s)

## Scope Paths

- `ai-agentic-embedded-base/specs/mcp_tasks.md`
- `ai-agentic-embedded-base/specs/zeroclaw_dual_hw_todo.md`
- `specs/mcp_tasks.md`
- `specs/zeroclaw_dual_hw_todo.md`
- `tools/ai/integrations/n8n/README.md`
- `tools/ai/integrations/n8n/kill_life_smoke_workflow.json`
- `tools/ai/zeroclaw_integrations_down.sh`
- `tools/ai/zeroclaw_integrations_import_n8n.sh`
- `tools/ai/zeroclaw_integrations_status.sh`
- `tools/ai/zeroclaw_integrations_up.sh`

## Canonical Checks

```bash
cd /home/clems/Kill_LIFE && bash tools/test_python.sh --suite stable
cd /home/clems/Kill_LIFE && python3 tools/validate_specs.py --json
git -C /home/clems/Kill_LIFE diff --check
```

## External Blockers After Local Lots

- `Anthropic`: cle presente mais credit insuffisant sur l'API
- `Google Gemini`: cle presente mais `generativelanguage.googleapis.com` est desactive sur le projet associe
- sur le Mac cible, le worktree `/Users/electron/mascarade` reste dirty; ne pas faire de `git pull` tant que les changements locaux ne sont pas consolides
- si le sandbox `PLM` doit passer en live, il faut encore renseigner `AGENT_FACTORY_PLM_BASE_URL`, `AGENT_FACTORY_PLM_API_KEY` et les `AGENT_FACTORY_PLM_RESOURCE_*` sur la VM
- si le sandbox `QMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_QMS_BASE_URL`, `AGENT_FACTORY_QMS_API_KEY` et les `AGENT_FACTORY_QMS_RESOURCE_*` sur la VM
- si le sandbox `WMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_WMS_BASE_URL`, `AGENT_FACTORY_WMS_API_KEY` et les `AGENT_FACTORY_WMS_RESOURCE_*` sur la VM
- `DCS` est ferme localement sur un sandbox/runtime OT gouverne et un flux de demo executable; ne rouvrir un vrai DCS live qu'avec un runtime/contrat OT externe
