# Next Useful Lot State

Generated: 2026-03-09 05:52:05 CET

## Summary

- Detected lot: `kill-life-followup`
- Kind: `local`
- Primary repo: `Kill_LIFE`
- Primary root: `/home/clems/Kill_LIFE`
- Reason: Tracked local changes remain in Kill_LIFE and should be checked with the stable Python/spec suite.

## Repo Snapshot

- `mascarade`: 1 tracked delta(s)
- `crazy_life`: 0 tracked delta(s)
- `Kill_LIFE`: 19 tracked delta(s)
- `agent-factory-cockpit`: 0 tracked delta(s)

## Scope Paths

- `.github/prompts/plan_wizard_bulk_edit_hw.prompt.md`
- `Makefile`
- `README.md`
- `ai-agentic-embedded-base/specs/03_plan.md`
- `ai-agentic-embedded-base/specs/04_tasks.md`
- `ai-agentic-embedded-base/specs/README.md`
- `ai-agentic-embedded-base/specs/constraints.yaml`
- `docs/AI_WORKFLOWS.md`
- `docs/plans/09_plan_bulk_edit_hardware.md`
- `specs/03_plan.md`
- `specs/04_tasks.md`
- `specs/README.md`
- `specs/constraints.yaml`
- `tools/cockpit/README.md`
- `tools/cockpit/cockpit.py`
- `.github/ISSUE_TEMPLATE/`
- `tools/cockpit/lot_chain.sh`
- `tools/doc/readme_repo_coherence.sh`
- `tools/specs/`

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
