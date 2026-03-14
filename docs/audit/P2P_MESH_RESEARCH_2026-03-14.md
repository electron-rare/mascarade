# P2P Mesh Research Audit — 2026-03-14

## Scope

Wave `fine-tune / mesh P2P` focused on the live `ft-research` lane and the operator scripts around it.

The goal of this pass was:

- stop the live mesh audit from hanging indefinitely on stale or half-dead peers;
- reactivate a local fine-tune-capable worker on `GrosMac`;
- prove a real `distribute_task(capability="ft-research")` against the mesh;
- keep the audit trail scriptable and purgeable.

## Code changes applied

### Transport and protocol hardening

- `core/mascarade/p2p/protocol.py`
  - `writer.drain()` is now bounded by `_WRITE_TIMEOUT_SECONDS = 5.0`.
- `core/mascarade/p2p/transport.py`
  - each `PeerConnection.send()` is bounded by `_SEND_TIMEOUT_SECONDS = 6.0`;
  - `broadcast()` now sends in parallel and adds a second guard with `_BROADCAST_TIMEOUT_SECONDS = 7.0`.

These changes turn the previous live mesh failure mode from `indefinite hang` into `bounded timeout / degradable red`.

### Local bridge / worker runtime

- `core/scripts/p2p/node_start_bridge.py`
  - bootstrap default aligned to VM port `4002`;
  - local bridge now advertises `ft-research`, `ft-dataset`, `ft-teacher`, `ft-archive`;
  - local bridge now registers a real task handler for `ft-*`.
- `core/scripts/p2p/task_handler_worker.py`
  - `ft-*` capabilities are now delegated to `mascarade.finetune.p2p.task_handlers.handle_ft_task(...)`.
- `core/scripts/p2p/mesh_tui.py`
  - GrosMac capability map aligned with the research/archive lane.

### Operator scripts

- `core/scripts/p2p/run_all.sh`
  - VM bootstrap port aligned to `4002`;
  - local bridge detection no longer treats any open port as a valid mesh worker;
  - `research` command added for `ft-research`;
  - stdout is unbuffered for the probe subprocesses;
  - `test` and `research` now emit bounded results instead of freezing.
- `scripts/tui/p2p_mesh_review.sh`
  - local fallback port selection added;
  - port `4001` collision is now downgraded into a controlled fallback to `4101`;
  - review artifacts stay under `.ops/p2p-mesh-review/`.

## Live execution summary

### Environment facts

- local port `4001` was occupied by a non-mesh process (`com.docker`);
- the local fine-tune worker had to run on fallback port `4101`;
- the active local worker label during the successful probe was `GrosMac Research`.

### Successful live probe

The successful live probe sequence was:

1. start a local worker on `4101` with `ft-research,ft-dataset,ft-teacher,ft-archive`;
2. bootstrap a temporary node against VM peer `QmTO5AYG6ZT3EU3UWVLNWU2FFFHWKUJR7S` on `192.168.0.119:4002`;
3. resolve `find_capable_peers("ft-research")`;
4. run `distribute_task(..., capability="ft-research")`.

Observed result:

- peer discovered: `GrosMac Research`
- task status: `completed`
- claimed_by: `QmFI2BJ7Q4TRDAJYIEEORB3WGXCRID2FFN`
- first returned candidate: `Qwen/Qwen2.5-Coder-7B-Instruct`
- candidate count returned in the operator probe: `20`

This closes the critical proof point:

- `ft-research` can now be distributed across the live mesh and return Hugging Face search results without freezing the submitter node.

### Remaining degraded lanes

`task_test` is still not a green operator gate on the live mesh.

Observed degraded results:

- `compute` timed out
- `ft-validation` timed out
- `storage` timed out after claim by `QmLHOEMQ6IV3SY2A27OCTAGZ3UF2IHP4HR`

Interpretation:

- the mesh transport no longer wedges;
- `ft-research` is proved live;
- the generic task smoke still needs a separate follow-up on `compute`, `ft-validation`, and Tower storage completion.

## Test and probe commands used

Local targeted tests:

- `cd /Users/electron/mascarade/core && ./.venv/bin/python -m pytest -q tests/test_p2p_protocol.py tests/test_p2p_transport.py tests/test_p2p_tasks.py`

Live operator probe:

- temporary worker on `4101` using `scripts/p2p/task_handler_worker.py`
- temporary submitter node probing `find_capable_peers("ft-research")`
- `bash /Users/electron/mascarade/scripts/tui/p2p_mesh_review.sh run --yes --research-timeout 20`

## Cleanup

- `.ops/p2p-mesh-review/` artifacts were read and analyzed during the run;
- the local validation worker and the hanging wrapper processes were stopped after the evidence was extracted;
- the artifact directory should be purged once the conclusions above are captured in git.

## Next actions

1. turn `task_test` into a truthful gate for `compute`, `ft-validation`, and `storage`;
2. keep `ft-research` as the canonical live smoke for the fine-tune mesh lane;
3. use the green `ft-research` lane as the prerequisite for the next `Analyst` and `Archivist` steps.
