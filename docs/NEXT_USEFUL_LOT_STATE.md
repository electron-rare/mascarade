# Next Useful Lot State

Generated: 2026-03-09 05:38:46 CET

## Summary

- Detected lot: `industrial-dcs-governed-sandbox`
- Kind: `local`
- Primary repo: `agent-factory-cockpit`
- Primary root: `/home/clems/agent-factory-cockpit`
- Reason: The DCS sandbox lane is the only active industrial lot: local tracked changes cover the DCS contract, topology, sandbox runtime, cockpit UI, tests, and companion state docs.
- Companion repos: `mascarade,crazy_life`

## Repo Snapshot

- `mascarade`: 15 tracked delta(s)
- `crazy_life`: 1 tracked delta(s)
- `Kill_LIFE`: 9 tracked delta(s)
- `agent-factory-cockpit`: 21 tracked delta(s)

## Scope Paths

- `README.md`
- `Makefile`
- `agent_factory_cockpit/dcs_sandbox.py`
- `contracts/vendors/dcs/contract.yaml`
- `contracts/vendors/dcs/openapi.yaml`
- `docs/IMPLEMENTATION_TODO.md`
- `examples/dcs-governed-sandbox.json`
- `src/main.js`
- `src/styles.css`
- `tests/test_topology.py`
- `topology/dcs.yaml`

## Canonical Checks

```bash
cd /home/clems/agent-factory-cockpit && python3 -m py_compile serve.py agent_factory_cockpit/*.py scripts/lotctl.py
cd /home/clems/agent-factory-cockpit && python3 -m unittest tests.test_topology tests.test_validation tests.test_runtime -q
cd /home/clems/agent-factory-cockpit && python3 -m unittest tests.test_execution tests.test_mcp tests.test_dcs_sandbox tests.test_lotctl -q
cd /home/clems/agent-factory-cockpit && make demo-dcs-sandbox
git -C /home/clems/agent-factory-cockpit diff --check
```

## External Blockers After Local Lots

- `Anthropic`: cle presente mais credit insuffisant sur l'API
- `Google Gemini`: cle presente mais `generativelanguage.googleapis.com` est desactive sur le projet associe
- sur le Mac cible, le worktree `/Users/electron/mascarade` reste dirty; ne pas faire de `git pull` tant que les changements locaux ne sont pas consolides
- si le sandbox `PLM` doit passer en live, il faut encore renseigner `AGENT_FACTORY_PLM_BASE_URL`, `AGENT_FACTORY_PLM_API_KEY` et les `AGENT_FACTORY_PLM_RESOURCE_*` sur la VM
- si le sandbox `QMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_QMS_BASE_URL`, `AGENT_FACTORY_QMS_API_KEY` et les `AGENT_FACTORY_QMS_RESOURCE_*` sur la VM
- si le sandbox `WMS` doit passer en live, il faut encore renseigner `AGENT_FACTORY_WMS_BASE_URL`, `AGENT_FACTORY_WMS_API_KEY` et les `AGENT_FACTORY_WMS_RESOURCE_*` sur la VM
- lot actif: fabriquer un sandbox/runtime OT gouverne local pour `DCS`, l'integrer a la lane industrielle, puis ne rouvrir un vrai DCS live qu'avec un runtime/contrat OT externe
