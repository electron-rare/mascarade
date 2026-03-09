# Next Useful Lot State

Generated: 2026-03-09 05:54:19 CET

## Summary

- Detected lot: `external-only`
- Kind: `external`
- Primary repo: `none`
- Primary root: `-`
- Reason: No tracked local implementation lot is open. Only external blockers or operator-side actions remain.

## Repo Snapshot

- `mascarade`: 1 tracked delta(s)
- `crazy_life`: 0 tracked delta(s)
- `Kill_LIFE`: 0 tracked delta(s)
- `agent-factory-cockpit`: 0 tracked delta(s)

## Scope Paths

- none (no local lot detected)

## Canonical Checks

- none; only external blockers remain

## External Blockers After Local Lots

- `Anthropic`: cle presente mais credit insuffisant sur l'API
- `Google Gemini`: cle presente mais `generativelanguage.googleapis.com` est desactive sur le projet associe
- sur le Mac cible, le worktree `/Users/electron/mascarade` reste dirty; ne pas faire de `git pull` tant que les changements locaux ne sont pas consolides
- si le sandbox `PLM` doit passer en live, il faut encore renseigner `AGENT_FACTORY_PLM_BASE_URL`, `AGENT_FACTORY_PLM_API_KEY` et les `AGENT_FACTORY_PLM_RESOURCE_*` sur la VM
- si le sandbox `QMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_QMS_BASE_URL`, `AGENT_FACTORY_QMS_API_KEY` et les `AGENT_FACTORY_QMS_RESOURCE_*` sur la VM
- si le sandbox `WMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_WMS_BASE_URL`, `AGENT_FACTORY_WMS_API_KEY` et les `AGENT_FACTORY_WMS_RESOURCE_*` sur la VM
- `DCS` est ferme localement sur un sandbox/runtime OT gouverne et un flux de demo executable; ne rouvrir un vrai DCS live qu'avec un runtime/contrat OT externe
