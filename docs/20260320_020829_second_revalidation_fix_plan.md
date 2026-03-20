## Second Revalidation Fix Plan

Timestamp: `2026-03-20T02:08:29+02:00`

Context:
- follow-up to [20260320_020650_second_live_revalidation_report.md](/home/vi/work/ratio1/repos/multi_node_launcher/docs/20260320_020650_second_live_revalidation_report.md)
- focused only on the issues still reproducible after the first remediation implementation pass

Goal:
- make migration stop/start behavior truthful and robust on real hosts
- make shared-machine status resolution instance-correct
- resolve confusing sticky state and topology state after recovery / remove-node flows
- polish the remaining UX problems that were clearly visible to a real operator

## Guiding Rules

- Preserve the default product model:
  - `standard` remains `1 machine = 1 edge node`
  - `expert` remains explicit and advanced-only
- Prefer truthful state over optimistic state.
  - If runtime state is unknown, show `unknown`, not `running`.
- Shared-machine views must be instance-derived, not machine-aggregated then copied to every instance.
- Migration timeout behavior must use the same timeout policy as the rest of the long-running deploy/prepare flows.
- Recovery flows must be idempotent.
  - repeating rollback after partial recovery must not make the machine worse

## Phase A: Fix Shared Timeout Plumbing

Objective:
- remove the hidden `30s` timeout from migration source stop and rollback source start

Why first:
- this is the main reason the real migration and rollback flows still fail visibly
- it also leaves the operator with contradictory reality vs UI state

Implementation:
- trace the command execution path used by:
  - migration source stop
  - migration source restart during rollback
  - any migration service apply/start path that still bypasses the newer timeout policy
- centralize timeout resolution for service lifecycle playbooks so all of these use the same helper
- apply the longer timeout floor already introduced for real machine preparation and long-running deploy operations
- ensure migration phase progress messages remain visible while these longer waits are happening

Likely code areas:
- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- any shared command runner helpers in [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- migration execution / rollback orchestration in [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)

Tests:
- extend [test_migration_execution.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_execution.py)
- extend [test_migration_finalization.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_finalization.py)
- add targeted unit coverage for timeout resolution helper behavior

Acceptance criteria:
- migration stop/start execution paths never hardcode `30s`
- migration execution and rollback use the resolved long-running timeout policy
- a timeout message, if it still happens, reflects the actual configured timeout
- live revalidation no longer fails only because the service lifecycle runner was capped at `30s`

Non-goals:
- not redesigning migration transfer semantics
- not changing archive or checksum logic in this phase

## Phase B: Fix Shared-Machine Status Attribution

Objective:
- ensure each instance on a shared machine gets only its own runtime status

Why second:
- this is the most misleading remaining operator-facing bug
- it contaminates multiple screens and can lead to destructive wrong assumptions

Implementation:
- audit how `Node Status & Info` maps remote service/container results back to logical instances
- require per-instance matching by resolved runtime identity:
  - `edge_node_service_name`
  - `mnl_docker_container_name`
  - `mnl_docker_volume_path` where relevant
- do not infer instance health from machine-level “some container is running”
- if a sibling runtime is missing, keep that instance at:
  - `never_deployed`, `stopped`, or `unknown`
  according to its own persisted/runtime evidence
- apply the same status resolution logic to:
  - grouped machine view
  - current configuration view
  - any summary counts shown on the main menu

Likely code areas:
- grouped status builders in [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- status refresh / inventory reconciliation logic in [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- service info retrieval playbooks only if they currently return insufficient per-instance identity

Tests:
- extend [test_machine_grouping.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_grouping.py)
- extend [test_r1setup_core.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_r1setup_core.py)
- add a dedicated shared-machine status test module if the current tests become too crowded

Acceptance criteria:
- one running service on a shared machine cannot mark sibling undeployed instances as running
- `View Configuration` and `Node Status & Info` show the same per-instance truth
- main menu summary counts reflect actual instance states, not copied machine state

Non-goals:
- not implementing discovery/import in this phase
- not changing helper naming rules

## Phase C: Reconcile Recovery State After Remote Success

Objective:
- make migration-plan state and top-level UI reflect real recovery outcomes after partial failures

Why third:
- after Phase A, many false failures should disappear
- what remains should be handled explicitly rather than left sticky

Implementation:
- define a recovery reconciliation rule:
  - if rollback restart succeeds and source runtime verifies healthy, plan status must become a recovery-success state rather than staying `rollback_failed`
- decide the exact terminal states:
  - `failed`
  - `rollback_in_progress`
  - `rolled_back`
  - `rollback_partially_recovered`
  - `executed`
  - `finalized`
- update main/deployment menu banners to reflect those states truthfully
- do not keep stale `last_error` text if the final recovered state is now healthy and authoritative
- ensure operator logs keep the original failure event even if the current plan state is later reconciled

Likely code areas:
- migration state persistence in [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- menu banner rendering in [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- operation logging in [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)

Tests:
- extend [test_migration_execution.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_execution.py)
- extend [test_migration_finalization.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_finalization.py)
- add plan-state transition assertions for partial failure then verified recovery

Acceptance criteria:
- if the source node is demonstrably healthy again after rollback, the persisted plan state does not remain a misleading hard failure
- main menu and deployment menu reflect the reconciled state
- operation logs still preserve the original failure event

Non-goals:
- not auto-finalizing migrations in this phase

## Phase D: Decide and Implement Topology Downgrade Policy

Objective:
- make single-instance-after-remove behavior explicit and predictable

Why fourth:
- this is currently more of a product ambiguity than a pure bug
- it should be resolved before more shared-machine features are added

Recommended policy:
- do not silently downgrade `expert` to `standard` during remove-node
- keep the machine in `expert` mode by default
- show a clear operator hint:
  - “This machine now has one remaining instance. Keep expert mode, or normalize back to standard?”
- implement normalization as an explicit action, not an implicit side effect

Why this policy:
- explicit transitions are safer
- automatic downgrade could rename runtime identities or surprise advanced users
- it preserves stable runtime names and avoids hidden topology churn

Implementation:
- document the rule in the CLI and operator docs
- optionally add a follow-up action or config-level prompt for normalization
- if normalization is deferred, show a non-blocking note in grouped views

Tests:
- extend [test_machine_registration.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_registration.py)
- extend [test_runtime_naming.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_runtime_naming.py)
- add remove-node tests for “last extra instance removed”

Acceptance criteria:
- remove-node behavior is consistent and documented
- runtime identities remain stable after remove-node
- operators are not surprised by silent topology changes

Non-goals:
- not adding automatic cross-config topology normalization

## Phase E: Add Missing Success Recaps And Reduce Confusing Screen States

Objective:
- improve operator confidence in successful machine prep and status refresh flows

Implementation:
- after `Prepare Machines`, show an explicit completion summary before returning to the menu:
  - prepared successfully
  - failed
  - skipped
- reduce aggressive redraw / clear behavior in `Node Status & Info` where practical
- revisit the top-level `✗ not deployed` wording for configs that intentionally track preserved/imported live nodes
- improve machine labels where only derived ids exist:
  - show a friendlier host-based label without hiding the canonical machine id

Tests:
- extend [test_r1setup_core.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_r1setup_core.py)
- extend [test_machine_grouping.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_grouping.py)

Acceptance criteria:
- prepare-machine flow ends with a visible success/failure recap
- imported/preserved running nodes are not described in a needlessly misleading way
- no-clear dev mode remains readable during status workflows

Non-goals:
- not redesigning the full main menu information architecture

## Phase F: Real-Host Revalidation

Objective:
- rerun the exact scenarios that failed in the second pass

Required scenarios:
1. prepare empty machine
2. migration plan
3. migration execute
4. rollback after forced or real failure
5. same-machine second-instance add
6. status refresh with one deployed and one undeployed sibling
7. remove extra sibling and inspect resulting topology state

Acceptance criteria:
- migration no longer fails due only to the `30s` lifecycle timeout
- rollback no longer reports failure if the source node is actually restored
- undeployed sibling instances stay undeployed in all UI surfaces
- remove-node outcome matches the documented topology policy

## Recommended Delivery Order

1. Phase A
2. Phase B
3. Phase C
4. Phase D
5. Phase E
6. Phase F

## Expected User-Visible Outcome

After these phases:
- migration and rollback should behave like real long-running operations, not short command wrappers
- shared-machine expert mode should feel safe and intelligible
- the UI should stop overstating health for undeployed sibling instances
- operators should see clearer completion and recovery messaging

## Implementation Results

### Phase A

Status:

- completed

Implemented:

- added a dedicated migration runtime timeout helper with the same `180s` minimum floor used for longer deploy/apply work
- migrated source stop and rollback source restart to that shared lifecycle timeout instead of the raw base timeout
- updated target migration runtime playbooks so:
  - `apply_instance.yml` uses the migration runtime timeout
  - `service_start.yml` uses the migration runtime timeout
  - verification probes such as `service_status.yml` keep the shorter probe timeout

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_migration_execution.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_execution.py)
- [test_migration_finalization.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_finalization.py)

Verification:

- `python3 -m unittest tests.test_migration_execution`
- `python3 -m unittest tests.test_migration_finalization`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- migration lifecycle steps no longer inherit the raw `30s` base timeout by default
- target verification probes remain shorter than apply/start lifecycle phases

### Phase B

Status:

- completed

Implemented:

- added execution-inventory-only runtime aliases so per-instance service/container/volume names survive playbook `vars_files` precedence
- added a shared runtime-resolution task and wired it into:
  - `apply_instance.yml`
  - `service_status.yml`
  - `service_start.yml`
  - `service_stop.yml`
  - `service_restart.yml`
  - `customize_service.yml`
  - `delete_edge_node.yml`
- added a shared service-presence probe so status and service-control playbooks can distinguish:
  - configured runtime exists
  - configured runtime is missing / undeployed
- confirmed on the live shared-machine test host that:
  - `nodea` resolves to `edge_node`
  - undeployed sibling `nodeb` resolves to `edge_node_nodeb`
  - status summary now reports `NOT FOUND` for `nodeb` instead of copying `nodea`'s running runtime

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [apply_instance.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/apply_instance.yml)
- [service_status.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/service_status.yml)
- [service_start.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/service_start.yml)
- [service_stop.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/service_stop.yml)
- [service_restart.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/service_restart.yml)
- [customize_service.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/customize_service.yml)
- [delete_edge_node.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/delete_edge_node.yml)
- [resolve_instance_runtime_vars.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/tasks/resolve_instance_runtime_vars.yml)
- [probe_instance_service_presence.yml](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks/tasks/probe_instance_service_presence.yml)
- [test_inventory_builder.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_inventory_builder.py)
- [test_structural_invariants.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_structural_invariants.py)

Verification:

- `python3 -m unittest tests.test_inventory_builder`
- `python3 -m unittest tests.test_structural_invariants tests.test_node_status_tracker`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`
- live repo-playbook validation against `/tmp/r1setup_two_instance_execution_inventory.yml`

Result:

- per-instance runtime names are no longer collapsed back to the default runtime inside instance-scoped operational playbooks
- shared-machine status checks can now distinguish a running primary instance from an undeployed sibling on the same host

### Phase C

Status:

- completed

Implemented:

- added rollback source-runtime verification after a restart error
- if rollback restart reports an error but the source instance verifies as `running`, the plan now reconciles to `rolled_back` instead of staying stuck in `rollback_failed`
- preserved failure history by:
  - logging the original rollback failure event
  - recording recovery metadata under `rollback_recovery`
  - clearing `last_error` only after recovery is confirmed
- marked reconciled rollback success events with `reconciled_after_error` in the operation log payload

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_migration_finalization.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_finalization.py)

Verification:

- `python3 -m unittest tests.test_migration_finalization tests.test_migration_execution`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- rollback no longer has to remain a hard failure if the source node is demonstrably healthy again
- migration plan state can now reconcile from restart-timeout noise back to a truthful `rolled_back` state while keeping failure history
