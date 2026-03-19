# Implementation Phase Log

This file tracks completed implementation phases for the multi-instance and migration work.

## Phase 0

Completed At: `2026-03-17T22:12:54+02:00`

### Goal

Establish safe configuration-layer seams before changing deploy, topology, or migration behavior.

### Scope Completed

- added initial schema-version scaffolding in configuration metadata
- centralized inventory normalization into reusable helpers
- added derived fleet-state helpers from legacy inventory data
- kept current Ansible inventory persistence compatible
- added modular test coverage in dedicated files for:
  - fleet-state derivation
  - config normalization and schema metadata round-trip

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_fleet_model.py`
- `mnl_factory/scripts/tests/test_config_roundtrip.py`
- `docs/20260317_214931_multi_instance_expert_mode_todo.md`
- `docs/20260317_221254_multi_instance_migration_implementation_plan.md`
- `docs/implementation_phase_log.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_fleet_model`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_config_roundtrip`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`

### Verification Results

- `tests.test_fleet_model`: passed
- `tests.test_config_roundtrip`: passed
- `tests.test_r1setup_core`: passed

### Notes

- No user-visible deploy or operations behavior was changed in this phase.
- Fleet state is currently derived in memory from legacy inventory rather than persisted as the execution source of truth.
- This phase is intended to reduce implementation risk for later topology and migration work.

## Phase 1

Completed At: `2026-03-17T22:43:07+02:00`

### Goal

Persist schema-aware fleet metadata alongside legacy config data so later empty-machine and migration features have durable state to build on.

### Scope Completed

- added persistent `fleet_state` support to configuration metadata JSON
- added `config_schema_version` handling in active config and config metadata
- added fleet-state normalization and merge helpers
- preserved legacy `hosts.yml` as the execution inventory format
- ensured persisted empty-machine records can survive config load/save
- added dedicated schema-upgrade and fleet-persistence test coverage

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_config_roundtrip.py`
- `mnl_factory/scripts/tests/test_schema_upgrade.py`
- `docs/implementation_phase_log.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_schema_upgrade`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_config_roundtrip`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_fleet_model`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`

### Verification Results

- `tests.test_schema_upgrade`: passed
- `tests.test_config_roundtrip`: passed
- `tests.test_fleet_model`: passed
- `tests.test_r1setup_core`: passed

### Notes

- `fleet_state` is now persisted in the per-config metadata sidecar, not in `hosts.yml`.
- Legacy inventory remains the execution source for current operations.
- This phase still avoids user-visible deploy, status, and operations changes.

## Phase 2

Completed At: `2026-03-17T22:46:56+02:00`

### Goal

Add topology-aware machine registration and fleet visibility without disrupting the existing standard node-configuration flow.

### Scope Completed

- added machine-registration support without immediate deployment
- added active-config shell creation for empty fleet configurations
- added topology selection for registered machines
- added best-effort machine-spec probing helper
- added persisted machine-record upsert support in fleet metadata
- added a fleet summary view
- added configuration-menu entry points for:
  - register machine
  - fleet summary
- kept the existing standard node-configuration path intact

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_machine_registration.py`
- `docs/implementation_phase_log.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_machine_registration`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_schema_upgrade tests.test_config_roundtrip tests.test_fleet_model`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`

### Verification Results

- `tests.test_machine_registration`: passed
- `tests.test_schema_upgrade tests.test_config_roundtrip tests.test_fleet_model`: passed
- `tests.test_r1setup_core`: passed

### Notes

- Machine registration currently reuses the existing SSH connection capture flow to collect access details.
- Empty machines now persist in metadata and appear in fleet summaries even with no assigned instance.
- This phase introduces additive CLI functionality but still does not change deploy/runtime behavior.

## Phase 3

Completed At: `2026-03-17T22:49:42+02:00`

### Goal

Introduce a deterministic runtime naming engine and collision detection layer before deploy and migration flows start depending on runtime-name policy.

### Scope Completed

- added runtime-name sanitization for logical instance names
- added deterministic runtime-name resolution for:
  - `standard`
  - `expert`
  - `preserve`
  - `custom`
- added derived exit-status path support to runtime snapshots
- updated legacy runtime snapshot derivation to use the shared resolver
- added runtime collision detection across instances on the same machine
- added focused modular runtime-naming test coverage

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_runtime_naming.py`
- `docs/implementation_phase_log.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_runtime_naming tests.test_machine_registration tests.test_schema_upgrade tests.test_config_roundtrip tests.test_fleet_model`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`

### Verification Results

- runtime/fleet-focused suite: passed
- `tests.test_r1setup_core`: passed

### Notes

- Runtime naming is now centralized and testable, but deploy/runtime playbooks do not consume the new naming engine yet.
- This phase is intended to prevent later deploy and migration code from inventing names ad hoc.

## Phase 4

Completed At: `2026-03-17T23:01:53+02:00`

### Goal

Introduce an explicit helper-mode strategy so standard deployments keep their global helper scripts while expert-mode machines use an unambiguous dispatcher path.

### Scope Completed

- added centralized helper-mode resolution in `r1setup`
- added topology-aware remote helper command resolution for:
  - logs
  - node info
  - restart
  - node history
  - e2 pem retrieval
- added unsupported mixed-helper detection for one machine carrying both standard and expert helper semantics
- updated CLI log retrieval to use resolved remote helper commands instead of hardcoded `get_logs`
- added a shared expert-mode dispatcher script at `/usr/local/bin/r1service`
- added per-instance helper registry entries under `/var/lib/ratio1/r1setup/helpers`
- updated the node-info playbook to use topology-aware helper commands
- updated delete cleanup to remove per-instance helper registry entries and only remove global helper scripts in standard mode
- added focused modular test coverage for dispatcher/helper behavior

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_dispatcher_helpers.py`
- `mnl_factory/scripts/tests/test_structural_invariants.py`
- `mnl_factory/group_vars/mnl.yml`
- `mnl_factory/roles/setup/tasks/services.yml`
- `mnl_factory/roles/setup/tasks/render_edge_node_definition.yml`
- `mnl_factory/roles/setup/templates/get_node_info.command.j2`
- `mnl_factory/roles/setup/templates/r1service.j2`
- `mnl_factory/roles/setup/templates/r1service-instance.env.j2`
- `mnl_factory/playbooks/get_node_info.yml`
- `mnl_factory/playbooks/delete_edge_node.yml`
- `docs/implementation_phase_log.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_dispatcher_helpers`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_structural_invariants`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_runtime_naming tests.test_machine_registration tests.test_schema_upgrade tests.test_config_roundtrip tests.test_fleet_model`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`
- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m py_compile r1setup`

### Verification Results

- `tests.test_dispatcher_helpers`: passed
- `tests.test_structural_invariants`: passed
- runtime/fleet-focused compatibility suite: passed
- `tests.test_r1setup_core`: passed
- `python3 -m unittest discover tests`: passed
- `python3 -m py_compile r1setup`: passed

### Notes

- Standard-mode machines still use the existing global helper names such as `get_logs` and `get_node_info`.
- Expert-mode machines now install `r1service` plus per-instance registry files so multiple instances can coexist without helper entrypoint collisions.
- Mixed helper semantics on one machine are now rejected locally before deploy/customize/delete operations proceed.

## Phase 5

Completed At: `2026-03-17T23:15:42+02:00`

### Goal

Introduce generated per-operation inventories and split machine-level preparation from instance-level runtime application so multi-instance operations stop depending on one flat execution model.

### Scope Completed

- added generated execution inventory builders in `r1setup`
- added execution host enrichment for:
  - resolved runtime names
  - helper-mode fields
  - derived metadata paths
  - derived base-folder and local-cache paths
- added machine grouping and machine-dedup inventory generation
- added shared machine-scope and instance-scope extra-vars builders
- added a shared generated-playbook runner that writes and removes temporary execution inventories
- split CLI deployment into:
  - `prepare_machine.yml`
  - `apply_instance.yml`
- updated deployment flow to:
  - prepare each unique machine once
  - apply runtime definitions only to instances whose machine preparation succeeded
  - report machine-prep and instance-apply outcomes separately
- switched these flows to generated per-operation inventories:
  - deployment
  - delete
  - customize service / update service template
  - start / stop / restart service
  - service status checks
  - node info retrieval
- added focused modular test coverage for inventory building and generated playbook execution

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/playbooks/prepare_machine.yml`
- `mnl_factory/playbooks/apply_instance.yml`
- `mnl_factory/scripts/tests/test_inventory_builder.py`
- `mnl_factory/scripts/tests/test_r1setup_core.py`
- `mnl_factory/scripts/tests/test_structural_invariants.py`
- `docs/implementation_phase_log.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_inventory_builder`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_structural_invariants tests.test_runtime_naming tests.test_machine_registration tests.test_schema_upgrade tests.test_config_roundtrip tests.test_fleet_model tests.test_dispatcher_helpers`
- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m py_compile r1setup`

### Verification Results

- `tests.test_inventory_builder`: passed
- `tests.test_r1setup_core`: passed
- structural/runtime/fleet/dispatcher compatibility suite: passed
- `python3 -m unittest discover tests`: passed
- `python3 -m py_compile r1setup`: passed

### Notes

- `site.yml` remains in the repo as the legacy one-shot collection playbook, but the CLI deployment path now prefers the explicit machine-prep plus instance-apply sequence.
- Generated execution inventories now carry resolved runtime/helper values even when the legacy stored inventory does not yet persist all of them explicitly.
- Deployment can now continue on machines that prepared successfully even if another selected machine fails during the preparation phase.

## Phase 6

Completed At: `2026-03-19T19:49:56+02:00`

### Goal

Make machine and instance relationships visible in the CLI so empty machines, standard machines, and expert-mode multi-instance machines no longer appear as one flat unrelated host list.

### Scope Completed

- added grouped machine/instance view builders in `r1setup`
- added grouped machine status summarization for:
  - empty machines
  - single-instance standard machines
  - multi-instance expert machines
  - mixed per-machine instance states
- updated `Fleet Summary` to render grouped machine views with:
  - topology mode
  - deployment state
  - machine specs
  - nested instance runtime identities
- updated `Node Status & Info` to render grouped machine views with:
  - machine-level grouping
  - nested instance statuses
  - inline service-version health
  - last-update and SSH-auth details per instance
- updated `Deployment Status` to render grouped machine views instead of a flat host list
- added focused modular test coverage for:
  - grouped fleet view derivation
  - standard-mode compatibility when service names contain numeric suffixes
  - grouped display-line formatting

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_machine_grouping.py`
- `mnl_factory/scripts/tests/test_r1setup_core.py`
- `mnl_factory/scripts/README_r1setup.md`
- `docs/20260317_221254_multi_instance_migration_implementation_plan.md`
- `docs/implementation_phase_log.md`
- `AGENTS.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_machine_grouping`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`
- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m py_compile r1setup`

### Verification Results

- `tests.test_machine_grouping`: passed
- `tests.test_r1setup_core`: passed
- `python3 -m unittest discover tests`: passed
- `python3 -m py_compile r1setup`: passed

### Notes

- Standard mode remains concise and unchanged in behavior; the new grouping only changes how machine and instance relationships are rendered.
- Empty registered machines are now visible in the main grouped fleet/status views instead of disappearing behind host-only rendering.
- Acceptance criteria for the visualization phase are met:
  - empty machines render clearly
  - expert-mode machines render as grouped instances
  - topology mode and capacity context are visible when known
  - mixed states on one machine no longer look like unrelated separate hosts

## Phase 7

Completed At: `2026-03-19T19:58:28+02:00`

### Goal

Allow useful machine-scope operations on registered machines that do not yet have any assigned instance, without creating placeholder nodes or reusing the instance deployment path incorrectly.

### Scope Completed

- added registered-machine execution inventory builders in `r1setup`
- added a machine-only generated playbook runner for registered fleet machines
- added machine-selection UX for registered empty machines
- added `Prepare Registered Machines` in the deployment menu
- implemented machine-only preparation against `prepare_machine.yml`
- updated machine deployment-state persistence so machine-only operations can mark:
  - `prepared`
  - `error`
- updated main-menu suggestion logic so configs with only registered machines no longer misleadingly suggest node configuration first
- added focused modular test coverage for:
  - registered machine execution inventory building
  - machine-only generated playbook execution
  - empty-machine preparation state updates

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_inventory_builder.py`
- `mnl_factory/scripts/tests/test_empty_machine_operations.py`
- `mnl_factory/scripts/README_r1setup.md`
- `docs/20260317_221254_multi_instance_migration_implementation_plan.md`
- `docs/implementation_phase_log.md`
- `AGENTS.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_inventory_builder`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_empty_machine_operations`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`
- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m py_compile r1setup`

### Verification Results

- `tests.test_inventory_builder`: passed
- `tests.test_empty_machine_operations`: passed
- `tests.test_r1setup_core`: passed
- `python3 -m unittest discover tests`: passed
- `python3 -m py_compile r1setup`: passed

### Notes

- The machine-preparation flow is additive and does not change the default standard deployment path.
- Registered machines can now be prepared without inventing instance hosts or mutating the stored node inventory.
- Acceptance criteria for the empty-machine phase are met:
  - registered empty machines can be selected and prepared without placeholder instances
  - machine-only operations update machine state through fleet metadata
  - the machine-scope execution path is test covered

## Phase 8

Completed At: `2026-03-19T22:32:03+02:00`

### Goal

Add a planning-only migration workflow so operators can assemble, review, and save a migration plan before any source shutdown, assignment switch, or data transfer occurs.

### Scope Completed

- added migration-plan persistence in config metadata
- added a dedicated `MigrationPlanner` in `r1setup`
- added migration-planning flow in the deployment menu
- added source-instance selection and target-machine selection UX
- added target runtime-name policy selection for:
  - `preserve`
  - `normalize_to_target`
  - `custom`
- added migration-plan validation for:
  - source assignment validity
  - target machine existence
  - target standard-mode occupancy
  - target runtime collisions
  - controller temp-space availability
  - source volume size probe
  - target free-space probe
- added explicit transfer-route planning as:
  - `source machine -> local temp -> target machine`
- added focused modular test coverage for:
  - migration-plan persistence
  - successful plan assembly
  - blocked-plan validation
  - saved-plan flow

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_migration_planning.py`
- `mnl_factory/scripts/README_r1setup.md`
- `docs/20260317_221254_multi_instance_migration_implementation_plan.md`
- `docs/implementation_phase_log.md`
- `AGENTS.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_migration_planning`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core tests.test_inventory_builder tests.test_empty_machine_operations`
- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m py_compile r1setup`

### Verification Results

- `tests.test_migration_planning`: passed
- `tests.test_r1setup_core tests.test_inventory_builder tests.test_empty_machine_operations`: passed
- `python3 -m unittest discover tests`: passed
- `python3 -m py_compile r1setup`: passed

### Notes

- Migration planning is non-mutating: no source shutdown, assignment switch, archive creation, or transfer occurs in this phase.
- The saved plan now carries the exact target runtime names and controller-temp transfer path needed by execution.
- Acceptance criteria for the migration-planning phase are met:
  - a migration plan can be created and reviewed before touching remotes destructively
  - source/target conflicts are detected before execution starts
  - the transfer route explicitly uses controller temp storage
  - migration-planning behavior is test covered

## Phase 9

Completed At: `2026-03-19T22:48:16+02:00`

### Goal

Execute a saved migration plan safely through the controller temp folder and finalize the logical assignment only after verified target startup.

### Scope Completed

- added migration-execution flow in `MigrationPlanner`
- added deployment-menu entry for executing the saved migration plan
- added controller-routed archive transfer as:
  - source machine -> local controller temp folder
  - local controller temp folder -> target machine
- added execution-time safeguards for:
  - stale source/target machine assignments
  - local temp-folder initialization
  - local archive reset failures
  - source and target checksum verification
  - target volume ownership and permission verification
- added target runtime apply/start/verify sequence before assignment finalization
- added local operation-log entries for migration execution start, failure, and success
- updated migration execution to finalize inventory/fleet assignment only after target verification succeeds
- added focused modular test coverage for:
  - successful migration execution and finalization ordering
  - checksum-mismatch failure without assignment finalization

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_migration_execution.py`
- `mnl_factory/scripts/README_r1setup.md`
- `docs/20260317_221254_multi_instance_migration_implementation_plan.md`
- `docs/implementation_phase_log.md`
- `AGENTS.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_migration_execution`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_migration_planning`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`
- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m py_compile r1setup`

### Verification Results

- `tests.test_migration_execution`: passed
- `tests.test_migration_planning`: passed
- `tests.test_r1setup_core`: passed
- `python3 -m unittest discover tests`: passed
- `python3 -m py_compile r1setup`: passed

### Notes

- Migration execution now uses the required transfer route: source machine -> controller temp -> target machine.
- The source runtime is stopped before archive creation, and assignment stays unchanged until target verification succeeds.
- Source cleanup and rollback behavior remain deferred to Phase 10.
- Acceptance criteria for the migration-execution phase are met:
  - target preparation occurs before transfer when required
  - source stop happens before source archiving
  - controller temp storage is used before upload to the target
  - checksums are verified across the transfer stages
  - target verification succeeds before assignment finalization
  - migration execution behavior is test covered

## Phase 10

Completed At: `2026-03-19T22:55:35+02:00`

### Goal

Make migration recoverable under failure and make source cleanup explicit after verified success.

### Scope Completed

- added persisted migration execution step tracking through the saved plan state
- added `Rollback Migration` in the deployment menu for failed or interrupted plans
- added `Finalize Migration` in the deployment menu for executed plans
- added rollback flow that:
  - cleans target-side runtime artifacts conservatively
  - removes source/target/local archive artifacts
  - restarts the source runtime
  - keeps source assignment authoritative
- added finalization flow that:
  - cleans source-side runtime artifacts conservatively
  - optionally removes source volume data
  - removes source/target/local archive artifacts
  - keeps cleanup explicit after verified execution
- added local operation-log entries for rollback and finalization start, failure, and success
- added focused modular test coverage for:
  - successful rollback behavior
  - successful finalization behavior
  - persisted step/state transitions used by failure recovery

### Files Changed

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_migration_execution.py`
- `mnl_factory/scripts/tests/test_migration_finalization.py`
- `mnl_factory/scripts/README_r1setup.md`
- `docs/20260317_221254_multi_instance_migration_implementation_plan.md`
- `docs/implementation_phase_log.md`
- `AGENTS.md`

### Verification Commands

- `cd mnl_factory/scripts && python3 -m unittest tests.test_migration_execution tests.test_migration_finalization tests.test_migration_planning`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`
- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m py_compile r1setup`

### Verification Results

- migration-focused suite: passed
- `tests.test_r1setup_core`: passed
- `python3 -m unittest discover tests`: passed
- `python3 -m py_compile r1setup`: passed

### Notes

- Rollback/finalization intentionally avoid the machine-destructive `delete_edge_node.yml` path and only clean per-instance runtime artifacts plus temp archives.
- Controller-temp artifacts are now cleaned only during explicit rollback or finalization, not during uncertain execution state.
- Acceptance criteria for the rollback/finalization phase are met:
  - failed migration remains recoverable without manual reconstruction
  - source cleanup stays explicit and deferred until after verified success
  - migration state is visible enough through saved plan status and last-step tracking
  - local temp artifacts are cleaned explicitly after rollback/finalization
  - rollback/finalization behavior is test covered
