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
