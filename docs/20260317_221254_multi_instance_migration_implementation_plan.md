# Multi-Instance And Migration Implementation Plan

Created At: `2026-03-17T22:12:54+02:00`

## Goal

Implement:

- default `standard` mode with `1 machine = 1 edge node`
- optional `expert` mode with multiple instances per machine
- machine registration without immediate deployment
- future-safe migration of one logical instance from one machine to another

using maintainable Python and Ansible design, while preserving backward compatibility for current users.

## Current Status

Completed:

- Phase 0: safety baseline and config-layer refactor seams
- Phase 1: fleet metadata persistence
- Phase 2: machine registration and fleet summary foundation
- Phase 3: runtime naming engine and collision detection
- Phase 4: dispatcher-based helper strategy
- Phase 5: generated inventory and operation split
- Phase 6: visualization and fleet UX
- Phase 7: empty-machine operations
- Phase 8: migration planning framework

Not Started:

- Phase 9: migration execution
- Phase 10: rollback and finalization

## Recommended Next Step

The next best step is Phase 9: migration execution.

Reasoning:

- migration plans can now be built, reviewed, and saved locally without remote mutation
- source/target validation, target naming resolution, and controller-temp transfer routing are now explicit
- the next missing capability is executing the planned transfer safely and resumably

Practical goal for the next implementation slice:

- stop the source runtime at the correct moment, archive the source volume, and move it through the controller temp folder to the target machine
- keep assignment changes deferred until target verification succeeds
- make rollback/finalization explicit instead of implicit cleanup

### Immediate Phase 9 Breakdown

The next coding slice should be executed in this order:

1. execute the planned source shutdown and archive creation
2. transfer the archive via:
   - source machine -> controller temp folder
   - controller temp folder -> target machine
3. restore the target volume to the resolved target runtime path
4. start and verify the target runtime before any final assignment switch
5. add focused modular tests for execution sequencing, transfer routing, and verification guards
6. after the phase is complete:
   - update `docs/implementation_phase_log.md`
   - run targeted tests plus broad CLI regression
   - create a dedicated phase commit before moving on

### Immediate Deliverables For Phase 9

- one migration execution workflow driven by the saved or newly built plan
- explicit controller-temp transfer routing
- one focused test module for migration execution safeguards

### Exit Signal For Starting Phase 10

Do not start rollback/finalization work until all of the following are true:

- source data is not finalized away until target verification succeeds
- controller-temp transfer routing is used instead of direct machine-to-machine copy
- assignment switch happens only after target verification
- migration execution behavior is test covered

## Implementation Principles

- Preserve existing standard-mode behavior by default.
- Introduce explicit internal models instead of expanding raw dict manipulation.
- Keep logical instance identity separate from runtime service/container names.
- Treat machine-level and instance-level operations as different domains.
- Make migration rollback-safe and state-explicit.
- Prefer generated execution inventory from higher-level fleet state over using inventory as the only source of truth.
- Extend test coverage in a modular way across multiple focused test files instead of growing one monolithic test module.
- Add explicit schema versioning, lifecycle states, and operation locking before broad behavior changes.
- Prefer explicit, verified transfer steps over clever remote-to-remote shortcuts during migration.

## Scope Split

### In Scope For Initial Multi-Instance Foundation

- fleet model in r1setup
- machine registration without deployment
- standard/expert mode topology modeling
- grouped visualization
- expert-mode runtime naming
- expert-mode collision checks
- machine-level dedup during deploy/operations
- dispatcher-based helper strategy design and implementation scaffold

### In Scope For Migration Implementation

- moving one logical instance from machine A to machine B
- target-machine preparation
- source volume archive transfer and restore
- assignment finalization only after verification
- rollback-safe migration state

### Out Of Scope For First Pass

- live telemetry-based resource scheduling
- unmanaged remote service auto-import
- perfect transactional deploy semantics across multiple machines
- highly optimized streaming replication for migration

## Recommended Architecture

## 1. Persistent Model

Persist a fleet-oriented config model in r1setup.

Recommended top-level shape:

```yaml
fleet:
  machines:
    machine-a:
      ansible_host: 1.2.3.4
      ansible_user: root
      ansible_port: 22
      topology_mode: standard
      deployment_state: active
      machine_specs:
        cpu_total: 16
        memory_gb_total: 64
        last_checked_at: "2026-03-17T22:12:54+02:00"
    machine-b:
      ansible_host: 5.6.7.8
      ansible_user: root
      ansible_port: 22
      topology_mode: standard
      deployment_state: empty
  instances:
    node-1:
      logical_name: node-1
      assigned_machine_id: machine-a
      runtime_name_policy: preserve
      runtime:
        service_name: edge_node1
        container_name: edge_node1
        volume_path: /var/cache/edge_node1/_local_cache
        metadata_path: /var/cache/edge_node1/_local_cache/_data/r1setup/metadata.json
      resources:
        cpu_limit_cores: 4
        memory_limit_gb: 16
      status:
        node_status: running
        service_file_version: v1
```

Compatibility rule:

- existing host-centric inventories are loaded and normalized into this model in memory
- execution inventory is generated from this fleet model for playbook runs

### Required Schema Additions

Add explicit config versioning:

```yaml
config_schema_version: 1
fleet:
  ...
```

Rules:

- every persisted config must carry `config_schema_version`
- loading must go through a schema upgrader path
- one canonical in-memory model must be used after load, regardless of on-disk version
- save operations should write only the current schema version once migration logic is stable

### Config Migration Policy

- support reading legacy host-centric configs
- support upgrading older fleet-schema versions forward
- do not silently discard unknown future fields
- preserve deployment metadata and SSH metadata during upgrade
- add round-trip tests for every supported loader path

## 2. Python Internal Types

Implement small internal model helpers inside `mnl_factory/scripts/r1setup` first, then extract later only if needed.

Recommended types:

- `MachineRecord`
- `InstanceRecord`
- `RuntimeNames`
- `MachineSpecs`
- `FleetState`
- `MachineGroupView`
- `MigrationPlan`
- `OperationLock`

Recommended first implementation style:

- `@dataclass` where practical
- one conversion layer:
  - raw config dict -> typed objects
  - typed objects -> raw config dict

This avoids uncontrolled dict mutation across the CLI.

### Lifecycle State Enums

Define explicit enums or constant sets for:

- machine state:
  - `empty`
  - `registered`
  - `prepared`
  - `active`
  - `unreachable`
  - `error`
- instance state:
  - `never_deployed`
  - `assigned`
  - `deploying`
  - `running`
  - `stopped`
  - `migrating`
  - `deleted`
  - `error`
- migration state:
  - `planned`
  - `preparing_target`
  - `stopping_source`
  - `archiving_source`
  - `downloaded_to_local_temp`
  - `uploaded_to_target`
  - `restored_on_target`
  - `starting_target`
  - `verifying_target`
  - `finalized`
  - `rollback_available`
  - `rolled_back`
  - `failed`

Rule:

- state transitions should happen through helper functions, not arbitrary string mutation

## 3. Execution Model

Persist fleet state, but generate operation-specific Ansible inventory from selected machines/instances.

Rule:

- one operation builds only the inventory entries it needs
- machine-level playbooks target unique machines
- instance-level playbooks target selected instances with explicit extra-vars

### Required Builders

Add explicit builders rather than constructing command args ad hoc:

- `build_execution_inventory(...)`
- `build_machine_extra_vars(...)`
- `build_instance_extra_vars(...)`
- `build_migration_extra_vars(...)`

This avoids inventing fake inventory structure for empty machines while still allowing them to exist in r1setup state.

### Operation Locking

Add a local operation lock per active config.

Recommended behavior:

- long-running operations acquire a config-scoped lock
- migration acquires a stronger lock covering:
  - source machine
  - target machine
  - source instance
- overlapping conflicting operations should fail fast with a clear message

This prevents status refresh, deployment, migration, or update-service from mutating the same state concurrently.

## 4. Secrets And Sensitive Data Handling

The fleet model must not weaken current secret handling.

Rules:

- preserve current SSH password and sudo-password handling semantics
- never write secrets into generated debug output
- do not include secrets in migration audit summaries
- generated execution inventory files should only contain secrets when required for the operation
- local temporary migration artifacts must not contain plaintext secrets beyond the node data being transferred
- local temp paths used during migration must be permission-restricted

Recommended implementation:

- store only the minimum necessary auth fields in the persisted config
- keep masking rules centralized
- ensure export/import behavior for configs clearly documents whether secrets are included

## 5. Transfer Integrity And Disk Safety

Migration archive transfer must be explicitly verified.

Required checks:

- verify source volume path exists before stop/archive
- estimate or measure source archive size
- verify sufficient free disk space:
  - on machine A for archive creation
  - on the local controller temp folder
  - on machine B for upload and extraction
- generate checksum on source archive
- verify checksum after download to local temp
- verify checksum after upload to machine B
- verify extracted target path ownership and permissions

Do not skip these checks in the default migration flow.

## 6. Supported Transition Policy

Be explicit about supported topology transitions.

Supported transitions:

- legacy standard config -> fleet-model standard
- empty machine -> prepared machine
- empty machine -> assigned standard instance
- empty machine -> assigned expert instance set
- standard machine with one instance -> migration target for another logical instance only after explicit topology decision

Restricted transitions:

- standard machine with existing global helper assumptions -> expert-mode helper strategy change without explicit operator confirmation
- helper behavior changes must always be explained before activation

## 7. Dry-Run, Resume, And Health Policy

These should be decided before broad implementation starts.

### Dry-Run Policy

Add a dry-run mode for operations with meaningful planning or destructive impact:

- machine preparation
- expert-mode deploy planning
- naming resolution
- service update on selected instances
- delete planning
- migration planning and execution preview

Dry-run behavior:

- no remote mutation
- no persisted assignment change
- no source stop
- no archive creation
- show resolved runtime names, targets, transfer path, and intended steps

### Resumable Operation Policy

Long-running operations should persist enough state to be resumed or explained after interruption.

Required for:

- migration
- grouped deploy operations with machine-level prep
- delete flows with partial completion

Recommended behavior:

- persist current operation id and phase
- persist last completed step
- on CLI restart, detect incomplete operation state
- offer:
  - inspect state
  - resume if safe
  - roll back if supported
  - clear stale state only with explicit confirmation

### Health-Check Policy

Define migration/deploy verification at two levels:

1. Runtime-level checks
- systemd unit active
- expected container name running

2. App-level checks
- `get_node_info` or equivalent command returns successfully when available

Recommended rule:

- runtime-level checks are mandatory
- app-level check should be attempted and reported
- migration finalization should require at least runtime-level success and should use app-level success when available as a stronger confidence signal

## 8. Archive Content And Controller Temp Policy

### Archive Content Policy

Do not leave migration archive contents implicit.

Define whether migration copies:

- full persistent volume root
- selected subpaths only
- excludes known transient paths such as logs, caches, temp files, or regenerated artifacts

Recommended first version:

- archive the full persistent instance volume unless there is a proven safe exclusion list
- document any exclusions explicitly
- keep archive path generation centralized

### Controller Temp Folder Policy

Because migration transfers go through the controller machine, define a local temp policy.

Requirements:

- temp root must be configurable
- default temp root should live under a launcher-controlled path, not an ad hoc shell temp path
- temp directory permissions must be restrictive
- archive filenames must be unique, sanitized, and traceable to operation id
- cleanup should happen:
  - after successful finalize
  - after rollback
  - or by age-based cleanup if interrupted state remains

Recommended metadata to store for local temp artifacts:

- operation id
- logical instance id
- source machine id
- target machine id
- checksum
- created_at
- cleanup_status

## 9. Unsupported-Case Matrix

Before implementation, document and enforce unsupported or restricted cases.

Examples:

- migration into a target machine with unmanaged conflicting services
- migration while another lock is active on source or target
- switching helper strategy on a machine without explicit confirmation
- direct remote-to-remote transfer bypassing the controller temp path
- finalizing migration when target verification did not pass
- deleting shared machine assets while sibling instances remain

Recommended behavior:

- fail clearly
- explain why the case is unsupported or blocked
- show the operator the required corrective action

## 10. Operation Logging And Retention

Add an explicit local operation log for r1setup.

### Goals

- capture operator-visible operations
- record important inputs and resolved targets
- record outcomes, warnings, and failures
- support debugging and postmortem review
- avoid unbounded growth

### What To Log

Per operation, record:

- timestamp
- operation id
- operation type
- config name
- source machine / target machine / instance ids when relevant
- resolved runtime names
- transfer route for migration
- major phase transitions
- result:
  - success
  - failed
  - rolled_back
  - cancelled
- high-level error summary when applicable

### What Not To Log

- plaintext SSH passwords
- sudo passwords
- private key contents
- full raw archive contents
- sensitive environment values unless explicitly masked

### Storage Policy

Recommended log location:

- under the r1setup local config/state area in a dedicated logs directory

Recommended files:

- active operation log
- archived rotated logs

### Rotation And Cleanup Policy

Requirements:

- active log must be size-capped
- when the active log exceeds the configured threshold, rotate it into an archive file
- archived logs older than a configured number of days should be deleted automatically
- retention values should be configurable with sensible defaults

Recommended defaults:

- active log max size: modest, for example `10-20 MB`
- retention: for example `30 days`

### Logging Design Recommendation

- use structured line-oriented logging where practical
- keep one human-readable summary line per major event
- include operation ids so one migration or deploy can be reconstructed from the log stream
- expose a CLI view for recent operations later if useful

## File-Level Plan

## Phase 0: Safety Baseline And Refactor Entry Points

### Objective

Create safe seams before adding new behavior.

### Target Files

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_r1setup_core.py`
- `mnl_factory/scripts/tests/test_structural_invariants.py`

### Tasks

1. Add internal helpers for:
   - loading normalized fleet state
   - saving fleet state
   - generating execution inventory from fleet state
   - grouping instances by machine
2. Centralize runtime-name generation.
3. Centralize machine identity normalization.
4. Add schema version loader/upgrader entry points.
5. Add operation lock scaffolding.
6. Add operation logging scaffolding with rotation/cleanup helpers.
7. Add tests for normalization only, with no behavior changes yet.

### Gate To Exit Phase

- current standard-mode behavior unchanged
- current tests still pass
- legacy configs load and save correctly

### Acceptance Criteria

- Running the current standard-mode CLI flows produces no user-visible behavior regression.
- Legacy configurations can still be loaded, edited, and saved successfully.
- New normalization helpers exist and are covered by focused tests.
- Runtime naming and machine identity logic are centralized enough that new features do not need to duplicate ad hoc parsing logic.
- Config schema version is explicit and legacy loader paths are test-covered.
- Operation-lock scaffolding exists even if not yet used by every operation.
- Operation logging scaffolding exists with size-cap and retention behavior test coverage.

## Phase 1: Fleet Model Introduction

### Objective

Make machines first-class objects without breaking current configs.

### Target Files

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_r1setup_core.py`
- `mnl_factory/scripts/tests/test_module_helpers.py`

### Tasks

1. Add persistent fleet schema support:
   - `fleet.machines`
   - `fleet.instances`
2. Add compatibility normalization from current `gpu_nodes.hosts`.
3. Preserve current config file locations and activation flow.
4. Add machine records that can exist without any instance assignment.
5. Add save-path compatibility so current export/import workflows do not break immediately.
6. Add round-trip coverage for legacy -> current schema -> current schema reload.

### Design Notes

- do not remove legacy read support
- write new format only after compatibility logic is stable
- if dual-format support is needed temporarily, keep one canonical in-memory model

### Gate To Exit Phase

- empty machines can be represented in config
- legacy config with one or many hosts loads into fleet model
- no deploy behavior changed yet

### Acceptance Criteria

- The persisted config can represent a machine with zero assigned instances.
- Legacy host-centric configs normalize into the fleet model without losing deployment metadata.
- Saving and reloading the new model preserves machine and instance identities.
- No deployment, status, or operations behavior has been changed by fleet-model introduction alone.
- Legacy config upgrades are explicit, repeatable, and test-covered.

## Phase 2: Standard And Expert Configuration Flow

### Objective

Add machine registration and topology-aware configuration.

### Target Files

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_r1setup_core.py`

### Tasks

1. Extend configuration menu to separate:
   - add machine
   - add instance
   - assign instance to machine
   - register machine without deployment
2. Add topology selection:
   - `standard`
   - `expert`
3. Add hardware discovery helper for machine specs.
4. In expert mode:
   - ask how many instances should run on the machine
   - default each instance to `4 cores / 16 GB`
   - calculate recommended capacity
5. In standard mode:
   - preserve simple one-machine-one-instance workflow
6. Add transition-warning flow where a machine’s helper/runtime assumptions would change.
7. Add dry-run support for topology and deploy planning views where practical.

### UX Rules

- standard path should remain short
- expert path may be longer but explicit
- machine registration without deployment must be a first-class menu path

### Gate To Exit Phase

- user can add machine B without deploying
- machine B appears in fleet view
- no forced expert complexity in standard path

### Acceptance Criteria

- A user can register a new machine without creating or deploying an instance.
- The standard configuration path remains short and familiar for one-machine-one-node users.
- The expert path exposes topology, capacity, and instance-planning decisions explicitly.
- Registered empty machines are visible in CLI fleet views and can be selected for preparation or later assignment.
- Topology transitions that would alter helper behavior require explicit confirmation.
- Planning flows can run in dry-run mode without mutating config or remotes.

## Phase 3: Runtime Naming And Collision Engine

### Objective

Make runtime naming deterministic and migration-safe.

### Target Files

- `mnl_factory/scripts/r1setup`
- `mnl_factory/group_vars/mnl.yml`
- `mnl_factory/roles/setup/templates/edge_node.service.j2`
- `mnl_factory/roles/setup/templates/r1setup-metadata.json.j2`
- `mnl_factory/scripts/tests/test_structural_invariants.py`
- `mnl_factory/scripts/tests/test_r1setup_core.py`

### Tasks

1. Add naming resolver for:
   - service name
   - container name
   - volume path
   - metadata path
   - exit-status path
2. Add naming policies:
   - `preserve`
   - `normalize_to_target`
   - `custom`
3. Make service template consume explicit runtime names rather than default-only assumptions.
4. Make metadata include logical instance identity and assigned machine id.
5. Add collision detection before save/deploy/migrate.
6. Add naming-resolution support for migration targets with clear conflict outcomes.

### Important Rule

- logical instance name is stable identity
- runtime names are assignment-specific

### Gate To Exit Phase

- standard runtime names remain unchanged for legacy/standard deployments
- expert-mode names are unique and collision-checked

### Acceptance Criteria

- Existing standard deployments keep their current runtime names unless the operator explicitly changes them.
- Expert-mode runtime names are deterministic, unique on the target machine, and validated before deploy or migration.
- Logical instance identity remains stable even when runtime names differ between source and target machines.
- Service, container, volume, metadata, and exit-status paths are all resolved from the same naming policy logic.
- Naming resolution has deterministic behavior for collision cases: preserve, normalize, custom, or abort.

## Phase 4: Dispatcher-Based Helper Strategy

### Objective

Remove script ambiguity before multi-instance operations expand.

### Target Files

- `mnl_factory/roles/setup/tasks/services.yml`
- `mnl_factory/roles/setup/templates/get_logs.sh.j2`
- `mnl_factory/roles/setup/templates/get_node_info.command.j2`
- `mnl_factory/roles/setup/templates/restart_service.command.j2`
- new dispatcher template(s) under `mnl_factory/roles/setup/templates/`
- `mnl_factory/scripts/r1setup`
- tests under `mnl_factory/scripts/tests/`

### Recommended Implementation

Add dispatcher-style expert entrypoint:

- `/usr/local/bin/r1service`

Supported commands:

- `r1service <instance> logs`
- `r1service <instance> info`
- `r1service <instance> restart`
- `r1service <instance> history`
- `r1service <instance> get-e2-pem`

### Compatibility Rules

- standard mode keeps current global helpers
- expert mode installs dispatcher
- if a machine transitions toward expert semantics later, prompt before changing helper behavior

### Hard Decision

Supported path:

- standard machines keep current global helpers
- expert machines use dispatcher-style helper access

Do not support silent mixed helper semantics on the same machine.

### Gate To Exit Phase

- no helper collision in expert mode
- standard scripts still work in standard mode

### Acceptance Criteria

- Standard-mode machines retain current helper-script behavior.
- Expert-mode machines have unambiguous helper access with no entrypoint collisions.
- Dispatcher behavior is documented and test-covered.
- Transition warnings exist when a machine’s helper behavior would materially change.
- Unsupported mixed-helper states are rejected clearly instead of being guessed.

## Phase 5: Generated Inventory And Operation Split

### Objective

Separate machine-level and instance-level operations cleanly.

### Target Files

- `mnl_factory/scripts/r1setup`
- `mnl_factory/playbooks/site.yml`
- `mnl_factory/playbooks/service_start.yml`
- `mnl_factory/playbooks/service_stop.yml`
- `mnl_factory/playbooks/service_restart.yml`
- `mnl_factory/playbooks/service_status.yml`
- `mnl_factory/playbooks/customize_service.yml`
- `mnl_factory/playbooks/delete_edge_node.yml`

### Tasks

1. Add inventory generation for:
   - selected machines
   - selected instances
2. Split machine-preparation from instance-deployment conceptually:
   - machine prep: prerequisites/docker/NVIDIA
   - instance apply: service render/start/status
3. Ensure machine-level setup runs once per unique machine within one operation.
4. Keep instance-level start/stop/restart/status targeted to selected instances.
5. Route all playbook invocations through shared inventory and extra-vars builders.

### Important Detail

The current `site.yml` is host-driven. For the new model, either:

1. generate one inventory host per instance but mark machine-level roles to dedupe by machine identity

or

2. split into separate playbooks for machine prep and instance apply

Recommended approach:

- split playbooks conceptually, even if implementation starts with generated limits and extra-vars

### Gate To Exit Phase

- same-machine multi-instance deploy does not rerun prep redundantly
- status/start/stop/restart work per instance

### Acceptance Criteria

- Within one operation, machine-level preparation runs at most once per unique machine.
- Instance-level actions target only the selected logical instances.
- Generated execution inventory includes only the machines or instances relevant to the current operation.
- Partial failures are reported separately for machine-level and instance-level steps.
- All operation commands derive runtime names and extra-vars through shared builders rather than ad hoc string assembly.

## Phase 6: Visualization And Fleet UX

### Objective

Represent machines and instances correctly in the CLI.

### Target Files

- `mnl_factory/scripts/r1setup`
- `mnl_factory/scripts/tests/test_r1setup_core.py`

### Tasks

1. Replace flat “host list” assumptions with grouped views where appropriate.
2. Add fleet view showing:
   - machines with no instances
   - standard machines
   - expert machines with grouped instances
3. Update `Node Status & Info` to:
   - group by machine
   - show instance rows
   - show capacity info when available
4. Keep standard mode display simple and familiar.
5. Surface machine and operation state clearly enough to explain incomplete migration or pending rollback state later.

### Gate To Exit Phase

- machine B with no deployment is visible
- machine A with two instances renders as grouped
- standard one-machine-one-node display still reads cleanly

### Acceptance Criteria

- Fleet views show empty machines, standard machines, and expert-mode grouped machines correctly.
- `Node Status & Info` distinguishes machine context from instance context.
- Standard-mode users do not see unnecessary expert-only complexity in the primary display.
- Mixed states on one machine, such as one running and one stopped instance, are rendered clearly.
- Incomplete operation or migration state is visible enough that the operator can understand what happened.

## Phase 7: Empty-Machine Operations

### Objective

Support fleet management before deployment.

### Target Files

- `mnl_factory/scripts/r1setup`
- possibly new playbooks for machine preparation/testing

### Tasks

1. Add “prepare machine” operation without deploying an instance.
2. Add “test machine connectivity/specs” for empty machines.
3. Allow operators to pre-stage a machine for later migration or assignment.
4. Add free-space/spec checks that can be reused by migration preflight.
5. Define and store controller temp-folder location/settings.

### Gate To Exit Phase

- user can register machine B
- user can prepare machine B
- user can leave machine B empty until later

### Acceptance Criteria

- A machine can be connectivity-tested and prepared before any instance is assigned to it.
- Preparation of an empty machine does not implicitly deploy an instance.
- The machine remains selectable later as a migration target or new assignment target.
- Machine preparation surfaces enough facts to support later migration preflight checks.
- Controller temp-folder policy exists before migration execution begins.

## Phase 8: Migration Planning Framework

### Objective

Add explicit migration planning before data transfer.

### Target Files

- `mnl_factory/scripts/r1setup`
- new tests under `mnl_factory/scripts/tests/`

### Tasks

1. Add migration menu:
   - select logical instance
   - select source machine
   - select target machine
2. Validate preconditions:
   - target machine reachable
   - no naming collisions
   - target prepared or preparable
   - source assignment valid
3. Add naming resolution step:
   - preserve
   - normalize to target
   - custom target runtime names
4. Add transfer-path planning:
   - source archive path on machine A
   - local temp folder on controller machine
   - upload path on machine B
5. Persist in-progress migration plan state locally.
6. Add preflight checks:
   - source archive size
   - local temp free space
   - target free space
   - checksum plan
7. Add unsupported-case validation with explicit operator-facing errors.

### Gate To Exit Phase

- migration plan can be created and reviewed before touching remotes

### Acceptance Criteria

- The user can select source instance, source machine, and target machine explicitly.
- The plan detects target naming/path collisions before remote mutation starts.
- The plan shows the exact resolved target runtime names before confirmation.
- No assignment change or source shutdown occurs during planning alone.
- The plan shows the transfer route explicitly as `machine A -> local temp -> machine B`.
- Disk-space and checksum preflight requirements are validated before execution begins.
- Unsupported or blocked cases fail during planning with explicit reasons.

## Phase 9: Migration Execution

### Objective

Move one logical instance safely from A to B.

### Target Files

- `mnl_factory/scripts/r1setup`
- new or updated playbooks for remote archive/restore
- helper templates if needed

### Tasks

1. Prepare target machine B fully.
2. Stop source instance on machine A.
3. Create source archive from resolved volume root.
4. Download source archive from machine A to a local temp folder on the controller machine.
5. Verify checksum in the local temp folder.
6. Upload the archive from the local temp folder to machine B.
7. Verify checksum on machine B.
8. Extract to resolved target volume path.
9. Verify extracted ownership and permissions.
10. Apply target runtime definition.
11. Start target instance.
12. Verify basic health:
   - systemd active
   - container running
   - optional node info returns
13. Finalize assignment in r1setup only after verification.
14. Write operation result summary to the local operation log.

### Implementation Detail

Use archive-based transfer first. Do not start with streaming sync or direct remote-to-remote copy.

Required transfer route:

- machine A -> controller local temp folder -> machine B

This gives better auditability, retry control, and checksum validation.

### Gate To Exit Phase

- successful A -> B move with updated assignment
- logical instance identity preserved

### Acceptance Criteria

- The target machine is prepared before source data transfer begins.
- The source instance is stopped before source volume archiving.
- The archive is downloaded to a permission-restricted local temp folder before upload to the target.
- The archive is restored to the resolved target path with correct runtime naming.
- Checksums and free-space validations pass at each transfer stage.
- Extracted target ownership and permissions are verified before startup.
- Target startup verification succeeds before assignment is finalized.
- The logical instance identity in r1setup remains the same after migration.
- The migration path and result are recorded in the local operation log without leaking secrets.

## Phase 10: Rollback And Finalization

### Objective

Make migration safe under failure.

### Target Files

- `mnl_factory/scripts/r1setup`
- migration-related playbooks/tests

### Tasks

1. If target verification fails:
   - keep source volume intact
   - offer restart on A
   - keep assignment unchanged
2. If target verification succeeds:
   - mark source as no longer assigned
   - optionally offer source cleanup
3. Keep migration audit markers in config/metadata.
4. Log rollback/finalization outcome to the local operation log.

### Gate To Exit Phase

- failed migration can be rolled back cleanly
- source cleanup does not happen before successful target verification

### Acceptance Criteria

- If target verification fails, the original assignment remains recoverable without reconstructing the instance manually.
- Source data and source runtime remain available for rollback until migration finalization succeeds.
- Cleanup of source artifacts is explicit and delayed until after successful verification.
- Migration state is visible enough in r1setup to explain whether a move is planned, in progress, rolled back, or finalized.
- Local temporary migration artifacts are cleaned up explicitly after finalize or rollback, not silently during uncertain state.
- Log records show whether the migration was finalized, rolled back, cancelled, or failed.

## Suggested Code Organization Inside `r1setup`

The file is already large. Do not implement all of this as more random methods.

Recommended internal organization, even if still in one file initially:

- fleet state helpers
- machine operations helpers
- instance operations helpers
- runtime naming helpers
- inventory generation helpers
- migration planning/execution helpers
- visualization helpers

Preferred extraction order if splitting files later:

1. `fleet_model.py`
2. `runtime_naming.py`
3. `inventory_builder.py`
4. `migration.py`

## Test Organization Strategy

Do not keep expanding a single large test file for this work.

Recommended approach:

- keep tests modular
- add new focused test files per subsystem
- keep existing broad regression tests, but move new specialized assertions into dedicated modules

Recommended new test modules:

- `test_fleet_model.py`
- `test_machine_grouping.py`
- `test_runtime_naming.py`
- `test_inventory_builder.py`
- `test_machine_registration.py`
- `test_expert_mode_planning.py`
- `test_dispatcher_helpers.py`
- `test_instance_operations.py`
- `test_migration_planning.py`
- `test_migration_execution.py`
- `test_schema_upgrade.py`
- `test_operation_locking.py`
- `test_transfer_integrity.py`
- `test_config_roundtrip.py`
- `test_operation_logging.py`

Recommended ownership of existing files:

- keep `test_r1setup_core.py` for broad CLI regression coverage and integration-style unit tests
- keep `test_structural_invariants.py` for template/script invariants
- keep `test_node_status_tracker.py` for status parsing/state transitions
- avoid putting all new fleet/migration coverage into `test_r1setup_core.py`

Test design rules:

- one main concern per test file
- shared builders/fixtures go into `tests/support.py`
- add small factory helpers for:
  - machine records
  - instance records
  - fleet state
  - migration plans
- prefer targeted tests for pure helper logic over only end-to-end style CLI tests
- keep regression tests for legacy standard-mode behavior in separate assertions from new expert-mode assertions
- add golden round-trip cases for config upgrade/save/reload behavior
- keep migration transfer-path logic testable without needing real remote copy in unit tests
- test log rotation and retention logic without relying on large real files

## Test Plan By Milestone

## Milestone A: Compatibility Refactor

Run:

- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- add tests for legacy config normalization in dedicated modules where possible
- add tests for schema upgrade and config round-trip behavior
- add tests for operation log rotation/cleanup helpers

Acceptance:

- no regression in standard mode

## Milestone B: Fleet And Empty Machines

Add tests:

- machine exists with zero assigned instances
- grouped view includes empty machine
- generated execution inventory excludes empty machine unless operation requires it
- schema-versioned fleet save/load round-trips cleanly

Preferred files:

- `test_fleet_model.py`
- `test_machine_registration.py`
- `test_inventory_builder.py`

Acceptance:

- machine B can be registered without deployment

## Milestone C: Expert Mode

Add tests:

- same machine hosts two instances
- runtime names unique
- helper behavior unambiguous
- capacity warnings triggered

Preferred files:

- `test_expert_mode_planning.py`
- `test_runtime_naming.py`
- `test_dispatcher_helpers.py`

Acceptance:

- expert mode works without breaking standard mode

## Milestone D: Migration Planning

Add tests:

- source/target validation
- naming collision detection
- no assignment change before verification
- local-temp transfer path planning is explicit
- disk-space/checksum preflight failures stop execution before source shutdown
- dry-run migration planning does not mutate config or remote state

Preferred files:

- `test_migration_planning.py`
- `test_runtime_naming.py`

Acceptance:

- migration plan is explicit and reviewable

## Milestone E: Migration Execution

Add tests:

- source stop before archive
- target prep before start
- successful finalize on verified target
- rollback on target failure
- archive download goes through local temp folder
- checksum verification happens after download and after upload
- local temp cleanup happens only after finalize or rollback
- operation logging records start/result without leaking secrets

Preferred files:

- `test_migration_execution.py`
- `test_instance_operations.py`

Acceptance:

- A -> B move preserves logical identity and protects source data until verified

## Risk Register

## Highest Risks

- trying to bolt migration directly onto the current flat host model
- helper-script ambiguity on mixed machines
- prematurely finalizing assignment during migration
- hidden collisions in volume/metadata/exit-status paths
- making standard mode more complex than it is today
- schema drift or lossy config upgrades
- secret leakage through generated inventories or debug output
- concurrent operations mutating the same instance or migration plan
- incomplete or corrupted local-temp transfer during migration
- unbounded operation log growth or missing retention cleanup
- non-resumable interrupted operations leaving operators without a clear recovery path

## Risk Mitigations

- introduce internal fleet model first
- adopt dispatcher strategy for expert mode
- make naming policy explicit
- make migration two-phase: plan -> execute -> finalize
- keep source cleanup strictly post-verification
- version the config schema and test upgrades/round-trips
- centralize masking and secret handling
- add operation locking before long-running mutation flows
- require checksum and free-space validation for migration transfer
- add resumable operation state for long-running flows
- rotate and age-prune operation logs automatically

## Recommended Delivery Order

Implement in this order:

1. compatibility refactor and fleet model
2. empty-machine registration
3. expert-mode naming and grouping
4. helper dispatcher
5. operation inventory generation and machine/instance split
6. migration planning
7. migration execution
8. rollback/finalization

This order minimizes architectural backtracking.

## Minimum Acceptance For “Ready To Start Coding”

Before coding feature behavior broadly, the implementation should have these decisions locked:

- fleet model shape
- canonical machine identity rule
- expert-mode helper strategy
- naming policy options
- migration finalization rule
- source-cleanup-after-verification rule
- config schema versioning and upgrader policy
- local-temp transfer route for migration
- operation-locking policy
- dry-run behavior for planning-heavy operations
- health-check threshold required for migration finalization
- operation log storage, rotation, and retention policy

Without those, implementation will likely fragment into hard-to-maintain special cases.
