## Second Live Revalidation Report

Timestamp: `2026-03-20T02:06:50+02:00`

Test machines:
- `34.88.90.109` (`r1-vi-g2`) as source / existing standard node host
- `35.228.69.214` (`r1-vi-g1`) as empty registered target machine

Config under test:
- repo-local `r1setup`
- dev home: `/tmp/r1setup-dev`
- config: `reval-devnet_20260320_0147_1n`
- environment: `devnet`

## Scenarios Executed

1. Registered `35.228.69.214` as an empty machine and probed specs.
2. Prepared the empty machine with `Prepare Machines`.
3. Planned migration from `nodea` on `34.88.90.109` to `machineb`.
4. Executed migration.
5. Rolled back the failed migration.
6. Added a second logical node on the same source machine to validate expert-mode gating.
7. Refreshed grouped status views.
8. Removed the second logical node and validated persisted cleanup.

## What Improved

- Expert-mode gating now works for same-machine add.
  - Adding `nodeb` on `34.88.90.109` correctly showed an explicit `Expert Mode Required` confirmation instead of silently creating a duplicate machine record.
- Shared-machine persistence is materially better.
  - After adding `nodeb`, both the YAML inventory and `active_config.json` stored a single machine entry `vitalii@34.88.90.109:22` with two instances.
  - `nodea` preserved its existing runtime names.
  - `nodeb` received unique generated runtime names such as `edge_node_nodeb`.
- Remove-node persistence is fixed compared with the previous round.
  - Removing `nodeb` deleted it from both the YAML inventory and `fleet_state.instances`.
  - The shared machine no longer kept a ghost instance reference.
- Machine spec messaging improved on the near-16 GiB host.
  - The UI now reported `15.6 GiB RAM` and explained that it was within the tolerated near-boundary range.
- Empty-machine preparation still works.
  - `35.228.69.214` ended the run with Docker installed and active, while remaining free of any `edge_node` service or container.

## Confirmed Remaining Problems

### 1. Migration execution still uses a 30s stop timeout

Migration failed during source stop with:

- `Command timed out after 30 seconds`
- playbook path: `playbooks/service_stop.yml`

Observed effect:
- source `edge_node` on `34.88.90.109` was stopped
- target machine was still clean
- plan status became `failed`

This means the timeout guidance improvements do not yet cover the migration stop/start execution path.

### 2. Rollback uses the same 30s start timeout

Rollback failed with:

- `Command timed out after 30 seconds`
- playbook path: `playbooks/service_start.yml`

Observed effect:
- source `edge_node` on `34.88.90.109` came back up successfully
- CLI still marked the rollback as `rollback_failed`
- `migration_plan_state.last_error` remained `Command timed out after 30 seconds`

So rollback recovery is operationally better than before, but the CLI still reports failure because the timeout path is shared.

### 3. Shared-machine status attribution is wrong

After adding `nodeb` but before deploying it, `Node Status & Info` showed:

- `nodea [RUNNING]`
- `nodeb [RUNNING]`

Remote validation showed:

- only `edge_node.service` existed
- `edge_node_nodeb.service` did not exist
- only container `edge_node` existed
- no `/var/cache/edge_node_nodeb` directory existed

This is a high-severity status-mapping bug. The grouped status path is attributing one live runtime to multiple logical instances on the same machine.

### 4. Current Configuration screen inherits the same false status

`View Configuration` also showed `nodeb` as:

- `[🟢 Running]`
- `service_file_version: v1`

That was incorrect and appears to be derived from the same shared-machine status mapping problem.

### 5. Shared machine remains marked `expert` after removing the second node

After deleting `nodeb`, persisted state was:

- one remaining instance: `nodea`
- machine `vitalii@34.88.90.109:22`
- `topology_mode: expert`

This may be acceptable if the design intentionally preserves expert mode until an explicit downgrade, but it currently feels implicit and unexplained from the operator perspective.

### 6. Failed migration state remains sticky after remote recovery

After rollback timed out but the source node recovered, the config still retained:

- `migration_plan_state.status = rollback_failed`
- `last_step = rollback_failed_source_restart`

The main menu and deployment menu continued to show a failed migration plan even though the real source node was healthy again.

## UX / Operator Notes

- `Prepare Machines` returned to the deployment menu without a visible success recap.
  - The machine was prepared correctly, but the operator never got a clear completion banner.
- Main menu still uses `✗ not deployed` for configs pointed at already-running imported/preserved nodes.
  - This is technically explainable but still misleading for operators.
- The raw derived machine id `vitalii@34.88.90.109:22` still appears beside friendly labels such as `machineb`.
  - This is better than duplicate-machine behavior, but still visually inconsistent.
- `Node Status & Info` still clears/redraws aggressively.
  - With `no-clear` dev mode enabled, this makes the flow feel less inspectable than the rest of the UI.

## Operation Log Evidence

Relevant log entries from `/tmp/r1setup-dev/.ratio1/r1_setup/logs/operations.log`:

```json
{"operation_type":"migration_execution","status":"started"}
{"operation_type":"migration_execution","status":"failed","details":{"message":"Command timed out after 30 seconds"}}
{"operation_type":"migration_rollback","status":"started"}
{"operation_type":"migration_rollback","status":"failed","details":{"message":"Command timed out after 30 seconds"}}
```

## Final Remote State

`34.88.90.109`
- `edge_node.service`: `active`
- `edge_node_nodeb.service`: not present / inactive
- running containers: `edge_node`

`35.228.69.214`
- Docker active
- no `edge_node` unit files
- no `edge_node` containers

## Recommended Fix Order

1. Fix the shared timeout path for migration stop/start and rollback start.
2. Fix shared-machine status attribution so undeployed sibling instances cannot inherit another instance's live state.
3. Decide and document the topology downgrade rule after removing the last extra instance.
4. Improve completion feedback for `Prepare Machines`.
5. Reconcile migration-plan sticky failure state after verified remote recovery.
