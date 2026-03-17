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
