# Multi-Machine Execution

## Goal

The execution hub can now route lots by machine or capability instead of
assuming everything must run on `photon-machine`.

## Scope Grammar

Each hub lot uses a `Portee` value:

- `global`
  - runnable on any machine
- `machine:<hostname>`
  - runnable only on that exact host
- `cap:<capability>`
  - runnable on any machine profile that declares that capability

Multiple scope tokens can be comma-separated and are treated as OR.

## Machine Profiles

Profiles live in [MACHINE_PROFILES.json](/mascarade/docs/MACHINE_PROFILES.json).

Example:

```json
{
  "machines": {
    "photon-machine": {
      "aliases": ["photon-machine"],
      "capabilities": ["docker-runtime", "lan-ops", "observability-local"]
    }
  }
}
```

To add another machine:

1. Add a new entry under `machines`.
2. Declare only real capabilities for that host.
3. Re-run the hub helpers from that machine.

## Commands

Show the current machine context:

```bash
cd /mascarade
scripts/current_machine_context.sh
scripts/current_machine_context.sh --json
```

Resolve the next useful lot for the current machine:

```bash
cd /mascarade
scripts/next_useful_lot.sh --json
scripts/chain_next_lot.sh --start --json
```

Resolve for another named machine profile:

```bash
cd /mascarade
scripts/next_useful_lot.sh --machine builder-01 --json
scripts/chain_next_lot.sh --machine builder-01 --start --json
```

Inspect all scopes without filtering:

```bash
cd /mascarade
scripts/next_useful_lot.sh --all-scopes --json
python3 scripts/execution_hub.py --all-scopes list
```

Show the dispatch matrix for every declared profile:

```bash
cd /mascarade
scripts/machine_lot_matrix.sh
scripts/machine_lot_matrix.sh --json
```

## Current Capability Routing

- `machine:photon-machine`
  - local VM/runtime and observability lots
- `net-runner`
  - logical profile for lots requiring `cap:network-online`
- `kicad-runner`
  - logical profile for lots requiring `cap:kicad-host`
- `nexar-runner`
  - logical profile for lots requiring `cap:nexar-live`
- `cap:network-online`
  - remote publication and internet-dependent checks
- `cap:kicad-host`
  - host-native KiCad validation
- `cap:nexar-live`
  - live Nexar validation with a real token

## Rule

Do not keep a lot in `BLOCKED` just because `photon-machine` cannot run it.
If another machine can legitimately own it, keep it `PENDING` and assign a
real `Portee`.
