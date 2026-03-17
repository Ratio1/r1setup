# Multi-Instance Expert Mode TODO

Created At: `2026-03-17T21:49:31+02:00`

## Purpose

Plan the addition of optional multi-instance Edge Node support on a single remote machine without changing the default current model.

This plan also needs to support future instance migration between registered machines.

## Core Product Decision

- Standard mode remains the default and remains `1 machine = 1 edge node`.
- Expert mode is an explicit advanced workflow for `1 machine = multiple edge node service instances`.
- Existing configurations and existing deployments must continue to behave as standard mode unless the operator explicitly creates or migrates to expert mode.
- Machines may exist in the fleet without any deployed Edge Node instance.
- Migration of a logical Edge Node instance from one machine to another is a supported future workflow and must influence the design now.

## Non-Negotiable Safeguards

- Do not infer topology mode from remote service names.
- A machine with a single service named `edge_node2` or `edge_node3` is still valid standard mode.
- Service name, container name, and volume path are opaque identifiers, not topology signals.
- Multi-instance support must be driven by explicit configuration metadata.
- Existing standard-mode deployments must not be renamed automatically.
- Existing helper script behavior must remain intact for standard mode.

## Required Metadata

Add explicit config metadata so topology is deterministic:

- `r1setup_topology_mode`: `standard` or `expert`
- `r1setup_machine_id`: stable identifier for the physical remote machine
- `r1setup_machine_label`: operator-facing machine label
- `r1setup_instance_id`: stable identifier for the logical service instance
- `r1setup_instance_index`: numeric index for display and generated defaults
- `r1setup_runtime_service_name`: configured systemd unit name
- `r1setup_runtime_container_name`: configured Docker container name
- `r1setup_runtime_volume_path`: configured persistent volume path
- `r1setup_runtime_metadata_path`: configured runtime metadata file path
- `r1setup_cpu_limit_cores`: configured CPU limit for this instance
- `r1setup_memory_limit_gb`: configured RAM limit for this instance
- `r1setup_machine_cpu_total`: discovered machine CPU total
- `r1setup_machine_memory_gb_total`: discovered machine RAM total
- `r1setup_machine_specs_last_checked_at`: ISO timestamp for the latest machine spec probe
- `r1setup_machine_deployment_state`: `empty`, `prepared`, `active`, `offline`, `unknown`
- `r1setup_assigned_machine_id`: the current machine assignment for a logical instance
- `r1setup_instance_logical_name`: stable logical name of the node instance inside r1setup
- `r1setup_runtime_name_policy`: `preserve`, `normalize_to_target`, or `custom`
- `r1setup_source_machine_id`: optional migration source metadata during in-progress moves

## Design Revision Triggered By Migration Requirement

The migration requirement means machines must become first-class objects in the configuration model.

The earlier instance-centric-only approach is still useful for compatibility, but it is not sufficient as the sole long-term source of truth because:

- the user must be able to register machines with no deployed node
- the user must be able to move one logical instance from machine A to machine B
- the user must be able to reason about fleet capacity independently of current deployments
- migration must update machine assignment without treating the move as delete-plus-recreate with lost identity

Recommended direction:

- keep compatibility with the current inventory-driven implementation
- introduce a higher-level fleet model in r1setup:
  - `machines`
  - `instances`
  - `assignments`
- generate operation-specific Ansible inventory from that higher-level model

This is a more maintainable design than storing all truth only in per-instance inventory hosts.

## Fleet Model

### Machines

Each machine record should represent a reachable remote host whether or not it currently runs an Edge Node.

Machine fields should include:

- stable machine identity
- SSH/auth details
- topology mode capability or preference
- discovered hardware facts
- machine preparation state
- launcher-managed runtime artifacts present on the machine

### Instances

Each instance record should represent a logical Edge Node identity independent of where it currently runs.

Instance fields should include:

- stable logical instance identity
- human-friendly logical instance name
- current assigned machine id
- runtime naming policy
- current runtime names on the assigned machine
- persistent volume identity
- current deployment/runtime state

### Assignments

Assignments map logical instances to physical machines.

This allows:

- empty fleet machines
- multiple instances on one expert-mode machine
- migration of one logical instance without losing identity
- better rollback semantics during moves

## Proposed Inventory Semantics

- Keep inventory entries instance-centric because current deployment, selection, and status flows already operate on inventory hosts.
- In standard mode:
  - one inventory host maps to one physical machine
  - one inventory host maps to one Edge Node instance
- In expert mode:
  - multiple inventory hosts may share the same `ansible_host`
  - those inventory hosts differ by instance metadata and runtime names
- Grouping in the UI should be derived from:
  - explicit `r1setup_machine_id` when present
  - otherwise a backward-compatible fallback based on the configured host identity

### Best-Practice Refinement

For long-term maintainability, the persisted fleet model should be richer than the generated Ansible inventory.

Recommended rule:

- fleet config is the source of truth
- generated inventory is an execution artifact for the selected operation

Benefits:

- supports empty machines naturally
- supports migration naturally
- reduces accidental coupling between runtime naming and persistent identity
- keeps Ansible focused on execution instead of becoming the only data model

## Design Decisions To Lock Before Implementation

These should be treated as recommended decisions unless a stronger alternative is adopted deliberately.

### 1. Canonical Machine Identity

- `r1setup_machine_id` should be the authoritative machine identity once present in config.
- For legacy configs without `r1setup_machine_id`, fallback grouping should use normalized connection identity:
  - `ansible_host`
  - `ansible_user`
  - `ansible_port`
- Remote hostname should be treated as diagnostic information, not as the canonical grouping key.
- If a machine's SSH target changes intentionally, the config migration/update path should either:
  - preserve the same `r1setup_machine_id` during edit
  - or make the operator confirm that the machine identity is being changed

### 2. Python Domain Model

The implementation should avoid spreading raw inventory-dict logic everywhere. Introduce internal typed concepts in Python such as:

- `MachineRecord`
- `ConfiguredInstance`
- `MachineGroup`
- `RuntimeNames`
- `MachineCapacity`
- `TopologyPlan`
- `MigrationPlan`

Recommended responsibilities:

- `MachineRecord`
  - machine-level source of truth
  - SSH/auth, hardware facts, prep state, topology mode
- `ConfiguredInstance`
  - logical Edge Node identity
  - holds assignment, metadata, and runtime naming policy
- `MachineGroup`
  - groups instances sharing one machine identity
  - owns machine-level facts and machine-level operations
- `RuntimeNames`
  - service/container/volume/metadata/helper naming rules
- `MachineCapacity`
  - discovered cores/RAM/GPU facts and capacity math
- `TopologyPlan`
  - derived view used by visualization, validation, and deployment planning
- `MigrationPlan`
  - source machine, target machine, instance, naming decision, rollback data, transfer paths

### 3. Helper Script Strategy

Recommended decision:

- Standard mode keeps current global helper scripts unchanged.
- Expert mode should use a dispatcher-style entrypoint as the primary interface.

Recommended expert command shape:

- `r1service <instance> logs`
- `r1service <instance> info`
- `r1service <instance> restart`
- `r1service <instance> history`

Optional convenience aliases may be added later, but should not be the primary architecture.

Reasons:

- fewer collisions
- fewer files to manage
- easier documentation
- easier compatibility logic
- easier to extend with new instance-aware subcommands
- easier migration because helper naming becomes less tied to the physical machine layout

### 4. Shared Asset Ownership

Machine-level assets must follow explicit ownership rules.

- Shared machine-level assets must never be deleted as a side effect of deleting one instance unless the operator explicitly requested machine purge.
- Machine-level shared assets should be cleaned up only when:
  - the operator selected a machine-purge action
  - or no launcher-managed instances remain on that machine and the cleanup path is explicitly the last-instance cleanup path
- Instance-level assets must always be removable independently.

### 5. Capacity Enforcement Philosophy

For the first version:

- CPU and RAM validation should be advisory-plus-confirmation, not falsely presented as a hard safety guarantee.
- The tool may warn or block by default, but expert users should be able to override with explicit confirmation.
- GPU facts should be displayed when discovered, but should not be overfit into a fake precise scheduling model in v1.

### 6. Failure Semantics

Implementation should define predictable behavior for:

- machine-level setup succeeds, instance deployment partially fails
- one instance is deleted while sibling instances remain
- spec discovery fails
- machine becomes unreachable after some instance operations succeeded
- status for sibling instances diverges on one machine

The CLI should not infer cleanup from partial success; it should preserve explicit state and report exactly what succeeded and what did not.

## Naming Model

The design should clearly separate three kinds of names:

### 1. Logical Instance Name

This is the stable r1setup-level identity of the node.

Examples:

- `node-1`
- `validator-a`
- `edge-node-berlin`

This should survive migration.

### 2. Machine Assignment

This is where the logical instance currently runs.

Examples:

- machine A
- machine B

This may change during migration.

### 3. Runtime Names

These are the concrete names on the target machine.

Examples:

- systemd service name
- Docker container name
- volume root path
- metadata path

These may or may not stay the same after migration depending on target mode and collisions.

### Naming Policy Recommendation

- The logical instance identity should always be stable across migration.
- Runtime names should be resolved per machine assignment.
- Migration should support these target policies:
  - `preserve`
  - `normalize_to_target`
  - `custom`

Recommended default behavior:

- if the target machine is empty and standard mode, default to normalized single-node names
- if the target machine is expert mode or already hosts instances, default to preserving index-aware uniqueness if no collision exists
- if a collision exists, force the operator to choose between:
  - a new target runtime name/index
  - aborting migration

This keeps logical identity separate from local runtime layout.

## Machine-Level Vs Instance-Level Ownership

This split should be explicit in both code and UI.

### Machine-Level

- SSH connection details
- SSH key management and password hardening
- connectivity checks
- host spec discovery
- Docker installation and daemon configuration
- NVIDIA driver and runtime setup
- machine-level cleanup of shared helper assets, if any

### Instance-Level

- service render and service file updates
- container name
- service name
- volume path
- metadata file content
- start, stop, restart
- logs
- node info lookup
- delete instance
- service version tracking
- resource limits

### Boundary Rules

- Machine-level operations should execute at most once per unique machine within a single orchestration run.
- Instance-level operations may execute independently for each selected instance.
- A failure in one instance-level operation must not automatically roll back or stop sibling instances unless the operator explicitly requested transactional behavior.
- A machine-level failure should mark all selected instances on that machine as impacted for the current operation.
- Migration should be modeled as an instance-level move that depends on machine-level preparation on the target.

## Resource Rules

- Store and document the minimum per-node requirement as `4 CPU cores` and `16 GB RAM`.
- In expert mode, discover machine specs before confirming deployment plan.
- Record total machine CPU cores and RAM.
- Default each new expert-mode instance to `4 cores / 16 GB`.
- Warn or block when requested instances exceed discovered machine capacity.
- Show remaining available capacity per machine in expert-mode visualization.

### Resource Policy Details

- First release should treat `4 cores / 16 GB` as the default and minimum recommended allocation per instance.
- If custom per-instance limits are allowed later, the planner must still validate against machine totals.
- Capacity math should be based on integer floor values:
  - `max_instances_by_cpu = floor(total_cores / 4)`
  - `max_instances_by_ram = floor(total_ram_gb / 16)`
  - `max_recommended_instances = min(max_instances_by_cpu, max_instances_by_ram)`
- If discovery fails in expert mode:
  - do not silently assume capacity
  - require explicit operator confirmation before continuing
- Standard mode should not require capacity discovery to preserve current low-friction behavior.

### Capacity Display Rules

- Capacity should be displayed as:
  - total machine capacity
  - planned allocated capacity across launcher-managed instances
  - remaining unallocated capacity
- The display should distinguish:
  - discovered current machine totals
  - configured planned instance limits
- The display should not claim knowledge of actual live process consumption unless real telemetry is explicitly implemented later.
- Fleet views should also show machines with zero assigned instances.

## Visualization Requirements

- Standard mode UI should continue to look like one machine, one node.
- Expert mode UI should group rows by physical machine and list service instances underneath.
- Status screens must distinguish:
  - machine identity
  - instance identity
  - service status
  - container status
  - configured resource limits
- Selections for deploy/start/stop/restart/update-service should remain instance-level.
- SSH, connectivity, and SSH hardening should be machine-level or machine-deduplicated.

### Display Requirements

- Standard mode row should continue to show the familiar:
  - node name
  - SSH target
  - status
  - service version state
- Expert mode machine header should show:
  - machine label
  - SSH target
  - topology mode
  - discovered cores and RAM
  - used vs available planned capacity
- Expert mode instance row should show:
  - logical node name
  - service name
  - container name
  - status
  - service version state
  - CPU/RAM limit

### Visualization Edge Cases

- A single machine with one oddly named service such as `edge_node3` must still render as standard mode.
- A machine with two configured instances on the same IP must render as one machine group with two instance rows.
- Mixed state on one machine must render clearly, for example one running instance and one stopped instance.
- If one machine is unreachable, all grouped instances should show the machine reachability failure without inventing per-instance transport differences.

## Service Naming Rules

- Standard mode may continue using existing names such as `edge_node`, `edge_node2`, or other operator-defined names.
- Expert mode must generate or require unique per-instance runtime names.
- Recommended expert defaults:
  - service: `edge_node1`, `edge_node2`, ...
  - container: `edge_node1`, `edge_node2`, ...
  - volume root: `/var/cache/edge_node1/_local_cache`, `/var/cache/edge_node2/_local_cache`, ...
- Do not assume numeric suffixes imply multi-instance mode.

## Script Creation Requirements

Current script creation is machine-global and will collide in expert mode. This must be redesigned carefully for:

- `get_logs`
- `get_node_info`
- `restart_service`
- `get_node_history`
- `get_e2_pem_file`
- legacy helper scripts such as `show.sh`, `restart.sh`, `stop.sh`

### Standard Mode

- Preserve existing machine-global helper script behavior for backward compatibility.
- Existing standard deployments should continue to work without operator changes.

### Expert Mode

Use one of these approaches:

1. Instance-specific script names
- `get_logs_edge_node1`
- `get_node_info_edge_node1`
- `restart_edge_node1`

2. A single dispatcher script with explicit target
- `r1service edge_node1 logs`
- `r1service edge_node2 restart`

Preferred direction:

- Keep standard mode scripts unchanged.
- Introduce instance-specific scripts or a dispatcher only for expert mode.
- Avoid ambiguous global scripts in expert mode unless they require an explicit instance argument.

### Script Design Constraints

- Never let expert-mode deployment overwrite a standard-mode global script on the same machine without an explicit compatibility decision.
- Prefer idempotent creation rules so re-applying one instance does not break the helper scripts for another instance.
- If a dispatcher is introduced, it must:
  - fail clearly when no instance is specified and multiple instances exist
  - optionally default to the only instance when exactly one launcher-managed instance exists
- Legacy `show.sh`, `restart.sh`, and `stop.sh` should either:
  - remain standard-mode only
  - or be replaced with explicit instance-aware variants in expert mode
- Expert mode should prefer one dispatcher file over many per-instance global entrypoints unless a strong operational reason is discovered otherwise.

### Script Acceptance Direction

- Standard mode:
  - `/usr/local/bin/get_logs` continues to work as today
  - `/usr/local/bin/get_node_info` continues to work as today
- Expert mode:
  - helper access must be unambiguous
  - no helper file for one instance may clobber another instance's helper entrypoint

### Recommended Compatibility Policy

- Standard mode and expert mode should not be mixed casually on the same machine unless the helper-script behavior is explicitly designed for coexistence.
- If a machine transitions from standard mode to expert mode in a future migration flow, the CLI should:
  - detect the helper-script compatibility boundary
  - explain what will change
  - require explicit confirmation before replacing or introducing helper entrypoints

## Migration Design

### Supported User Story

- A user can add one or more machines to the fleet without deploying an Edge Node on them.
- A user can select a logical instance currently running on machine A and migrate it to machine B.
- The r1setup configuration should be updated to reflect the new assignment while preserving logical identity.

### Migration Preconditions

Before migration starts, the tool should verify:

- source machine exists and the selected instance is assigned there
- target machine exists and is reachable
- target machine has no conflicting runtime name/path for the incoming instance
- target machine mode is understood:
  - empty standard target
  - empty expert target
  - existing expert target with sibling instances
- required tools exist or can be installed on target machine
- source instance can be safely stopped

### Migration Workflow

Recommended migration sequence:

1. create a local migration plan in r1setup
2. snapshot/copy relevant logical instance config inside r1setup before touching remotes
3. verify target naming policy and target runtime layout
4. prepare target machine fully:
   - prerequisites
   - Docker
   - NVIDIA/runtime support if needed
   - launcher helper/runtime support required for the target mode
5. stop the source instance on machine A
6. archive the source volume on machine A
7. transfer the archive to machine B
8. restore the archive into the resolved target volume path
9. render/install the target service with the resolved runtime names
10. start the instance on machine B
11. verify target startup and basic health
12. only after verification, finalize assignment in r1setup and mark source as migrated/stopped

### Rollback Philosophy

Migration should prefer rollback safety over aggressive cleanup.

- Do not delete the source volume immediately after a successful transfer.
- Do not remove source service/runtime artifacts until the target instance has started and basic verification passed.
- If target startup fails after source stop:
  - preserve source data
  - offer rollback by restoring the source service on machine A
- The CLI should keep explicit migration state until finalize or rollback is completed.

### Migration Naming Decisions

The migration flow must handle cases like:

- source runtime name is `edge_node1`
- target machine is empty and intended to remain standard mode
- target machine already has `edge_node1`

Recommended behavior:

- ask the operator whether the target should:
  - preserve the incoming runtime index/name if available
  - normalize to single-node naming on the new machine
  - use a custom target name
- always show the exact target runtime names before confirmation

### Migration Transfer Details

The first implementation may use archive-based transfer:

- stop source instance
- create archive from source volume root
- copy archive to target
- extract archive into target volume root

The transfer implementation should be:

- idempotent where practical
- explicit about temporary archive paths
- careful about permissions and ownership after extraction

### Migration Acceptance Direction

- moving one logical instance from A to B does not create a new logical instance identity
- source machine can remain in fleet after migration even if it becomes empty
- target machine can receive a migrated instance even if it had no previous deployment
- runtime naming on target is explicit and collision-checked
- the user sees a clear rollback option if the target start fails

## Playbook and Runtime Impacts

- Split machine-level preparation from instance-level deployment where needed.
- Avoid repeating Docker/NVIDIA/prerequisite work unnecessarily for multiple instances on the same machine.
- Ensure service status playbooks query the configured service and container names, not hardcoded defaults.
- Ensure delete logic distinguishes:
  - deleting one service instance
  - removing all launcher-managed instances from a machine
  - removing machine-level runtime helpers

### Runtime Design Details

- Exit status files should be instance-specific in expert mode to avoid `/tmp/ee-node.exit` collisions.
- Metadata files should be instance-specific and aligned with the configured volume root.
- Service templates should embed machine-readable identifiers for:
  - service file version
  - launcher-managed instance identity
  - optional machine identity when useful for diagnostics
- The status playbook output format should stay parseable even after adding grouping-related fields.
- `get_node_info` and related operational commands should target the configured container name, not a shared default.
- Migration temporary archive paths should be instance-specific and time-scoped to avoid clobbering sibling operations.

### Deployment Execution Rules

- Within one deploy operation targeting multiple instances on the same machine:
  - Docker/prerequisite/NVIDIA setup should run once per unique machine
  - service render/start should run per selected instance
- Retry behavior should be instance-aware:
  - a failed instance may be retried without reclassifying sibling instances as failed
  - a machine-level prerequisite failure may block all selected instances on that machine for that run
- The implementation should prefer deterministic idempotence over clever automatic recovery.

### Migration Execution Rules

- Machine B preparation should be completed before source data transfer starts.
- Source instance stop should happen as late as practical to minimize downtime.
- Assignment in config should not be finalized until target verification succeeds.
- Source cleanup should be an explicit finalization step, not an implicit side effect of initial success.

## Remote Discovery Requirements

Expert mode planning should gather per-machine facts such as:

- CPU core count
- total RAM
- hostname
- optional GPU presence and count
- currently existing launcher-managed services on the machine
- currently existing launcher-managed containers on the machine
- currently used launcher-managed volume roots on the machine

The first release should use that discovery for:

- planning capacity
- avoiding name/path collisions
- informing visualization

It should not auto-import unmanaged remote services into config.

## Migration Strategy

- Existing inventories load as `standard` automatically.
- No automatic runtime renaming for deployed services, containers, or volumes.
- Existing configs may receive default metadata fields during load/save normalization.
- Multi-instance behavior only activates when config metadata explicitly says `expert`.

### Migration Acceptance Requirements

- A legacy config with one host and service `edge_node` remains standard mode.
- A legacy config with one host and service `edge_node2` remains standard mode.
- A legacy config with several hosts on distinct IPs remains standard mode.
- Existing standard-mode update-service, start, stop, restart, and status flows must continue to work unchanged.
- Loading and saving an old config must not silently rewrite runtime names.

### Migration Design Improvement

- Machine-level discovered facts should not become independently editable truth in every sibling instance record without a normalization rule.
- If machine facts are persisted per instance for simplicity, the code should still treat one source as authoritative during save/update normalization.
- Prefer recomputing grouped machine views from instances instead of trying to persist two parallel truth models.
- Prefer persisting machine records separately from instance records once migration support begins.

## Implementation Phases

### Phase 1: Schema and Planning

- Add topology metadata to config/inventory model.
- Add compatibility normalization for old configs.
- Add constants for minimum resources per node.
- Add helper functions for grouping inventory entries into machine views.
- Introduce internal Python model helpers to reduce direct dict manipulation.
- Add machine records capable of existing without assigned instances.

### Phase 2: Expert Configuration Flow

- Add topology mode selection during configuration.
- Add machine capacity discovery.
- Add expert-mode instance planning UI.
- Add per-instance resource limit row with default `4 cores / 16 GB`.
- Add collision checks for service/container/volume/script names before saving configuration.
- Add machine registration flow that does not require immediate deployment.

### Phase 3: Runtime Naming and Scripts

- Generate unique service/container/volume names for expert-mode instances.
- Redesign helper script creation to avoid collisions.
- Preserve current helper script behavior for standard mode.
- Make exit-status and metadata paths instance-safe.

### Phase 4: Deployment and Operations

- Separate machine-level prep from instance-level service deployment.
- Update start/stop/restart/delete/update-service flows for instance targeting.
- Deduplicate machine-only operations.
- Define explicit delete semantics for instance deletion versus machine cleanup.
- Define partial-failure reporting rules for grouped operations.

### Phase 5: Visualization and Status

- Group status by machine in expert mode.
- Show per-instance rows and machine capacity summary.
- Keep standard mode presentation simple and unchanged.
- Show enough runtime identity to distinguish sibling instances on one machine.

### Phase 6: Tests and Docs

- Add unit tests for config migration and topology detection.
- Add tests for grouped visualization and resource validation.
- Add tests for helper script naming and no-collision guarantees.
- Update operator docs after behavior is implemented.
- Extend test coverage modularly across multiple focused test files instead of concentrating new coverage in one large test module.

### Phase 7: Migration

- Add migration planning flow for moving one logical instance between machines.
- Add target naming-policy selection and collision validation.
- Add archive transfer and restore workflow.
- Add rollback/finalization flow.
- Add migration-specific status and audit markers.

## Test Coverage Plan

### Unit Tests

- fleet model:
  - machine can exist without assigned instances
  - instance assignment can move from machine A to machine B
- config normalization:
  - legacy config defaults to `standard`
  - odd service names do not trigger expert mode
  - generated metadata is stable and deterministic
- grouping logic:
  - several instances on one IP group under one machine
  - distinct machines do not collapse accidentally
  - legacy grouping fallback uses normalized SSH target identity
- resource validation:
  - capacity math matches expected floor behavior
  - over-capacity plans trigger warning or block path
  - discovery failure path requires explicit confirmation
- runtime naming:
  - expert-mode generated service names are unique
  - expert-mode generated container names are unique
  - expert-mode generated volume paths are unique
  - standard mode preserves existing configured names
- script planning:
  - expert-mode helper generation does not collide
  - standard-mode helper generation remains unchanged
  - dispatcher resolution fails clearly when multiple instances exist and no target is supplied
- status parsing:
  - one running and one stopped sibling instance on the same machine parse correctly
  - machine unreachable state maps consistently across grouped instances
- delete planning:
  - deleting one instance does not select machine-wide cleanup by accident
  - machine cleanup option is only shown when appropriate
- migration planning:
  - source and target machine validation is explicit
  - target naming collision is detected
  - assignment is not finalized before target verification
  - rollback path preserves logical instance identity

### Structural Tests

- service template still exposes required machine-readable version markers
- expert-mode template additions remain parseable by status logic
- helper script templates include configured service/container identifiers
- no expert-mode helper path reuses a standard-mode global path by accident

### CLI Flow Tests

- configuration wizard:
  - standard mode path remains simple
  - expert mode path asks for topology, capacity, instance count, and limits
- selection UI:
  - grouped machine display stays readable
  - instance selection remains deterministic
- status UI:
  - standard mode still renders flat and familiar
  - expert mode renders grouped machine headers with instance rows

### Integration-Oriented Test Targets

- empty machine registration:
  - add machine B with no assigned instance
  - verify it appears in fleet view
- one machine with two configured instances:
  - deploy instance A and B
  - stop instance B
  - verify status shows A running and B stopped
- one machine with custom legacy service name:
  - verify it stays standard mode
  - verify no false multi-instance grouping is introduced
- two machines where one is expert-mode and one is standard-mode:
  - verify mixed topology display works
  - verify machine-level operations dedupe only where intended
- one machine with partial failure during grouped deployment:
  - machine prep succeeds
  - instance A succeeds
  - instance B fails
  - verify retry path can target only instance B
- migration A -> B:
  - source instance stops
  - target machine is prepared
  - archive transfers successfully
  - target starts
  - config assignment moves to B only after verification
- migration failure after transfer:
  - target start fails
  - source volume remains available
  - rollback can restart the source instance on A

### Test Structure Rule

- keep new coverage modular and subsystem-focused
- prefer multiple small test files over one large catch-all migration or fleet test file
- reuse `tests/support.py` for shared builders/fixtures
- keep broad regression coverage in existing core test files, but place new specialized logic in dedicated modules

## Acceptance Criteria

### Backward Compatibility

- Existing standard-mode users can configure, deploy, start, stop, restart, and check status without learning a new workflow.
- Existing hosts with custom service names like `edge_node2` still behave as standard mode.
- Existing script entrypoints continue to work for standard-mode deployments.
- Existing users can register extra machines without immediately deploying nodes to them.

### Expert Mode Behavior

- Operators can explicitly choose expert mode during configuration.
- Operators can plan multiple instances on one machine with explicit CPU/RAM defaults of `4 cores / 16 GB`.
- The planner detects and displays machine capacity before final confirmation when discovery succeeds.
- The planner warns or blocks when configured instances exceed recommended capacity.

### Deployment Semantics

- Within one deployment operation targeting multiple instances on the same machine, machine-level prerequisite/setup roles run at most once per unique machine.
- Each expert-mode instance gets a unique service name, container name, volume path, metadata path, and helper access path.
- Deleting one instance does not remove sibling instances or machine-level assets unless the operator explicitly chose that broader action.
- Partial failures are reported explicitly at machine level and instance level without inventing implicit rollback.

### Migration Semantics

- A logical instance can move from one registered machine to another without losing its logical identity in r1setup.
- The target machine may be empty before migration.
- The migration flow prepares the target machine before stopping the source instance where practical.
- The source instance is stopped before the source volume is archived.
- Assignment in r1setup changes only after target startup verification succeeds.
- If verification fails, the operator can roll back to the source machine without reconstructing the instance identity manually.

### Status and Visualization

- Standard mode status remains simple and flat.
- Expert mode status groups instances under their machine.
- Mixed instance states on one machine are visible and actionable.
- Service update recommendations remain instance-specific.

### Script Safety

- Standard mode keeps current helper behavior.
- Expert mode helper access is unambiguous and collision-free.
- No deployment of one expert-mode instance overwrites another instance's helper entrypoint unexpectedly.
- If dispatcher mode is adopted, invoking the dispatcher without an instance target on a multi-instance machine fails with a clear error.
- Migration between machines does not require the logical instance name to match the target runtime service/container name exactly.

## Verification Commands To Use During Implementation

- `cd mnl_factory/scripts && python3 -m unittest discover tests`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_r1setup_core`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_structural_invariants`
- `cd mnl_factory/scripts && python3 -m unittest tests.test_node_status_tracker`

Additional targeted tests should be added for the new topology and helper-script logic as implementation proceeds.

## Critical Risks To Re-Check During Implementation

- Backward compatibility for existing standard deployments
- False expert-mode detection from custom service names
- Helper script collisions on shared machines
- Over-deployment beyond machine CPU/RAM capacity
- Destructive delete behavior on machines with multiple instances
- Confusing UI when one IP address appears across several instance rows
- SSH hardening or machine-level actions accidentally repeating per instance
- Drift between persisted per-instance machine facts and grouped machine truth
- Overly broad fallback grouping that merges distinct machines accidentally
- Hidden helper-script compatibility problems when moving a machine from standard mode to expert mode
- Migration finalization happening before target verification
- Source cleanup happening too early during migration
- Treating logical instance identity and target runtime naming as the same concept

## Open Questions

- Should expert mode use instance-specific helper scripts, a dispatcher, or both?
- Should machine-level preparation be automatically deduplicated inside one deploy operation, or exposed as a separate explicit step?
- Should delete offer both `delete selected instance(s)` and `purge machine runtime artifacts`?
- Should expert mode allow custom per-instance limits beyond the default minimum, or keep the first version fixed at `4 cores / 16 GB`?
- Should expert mode expose currently discovered remote unmanaged `edge_node*.service` units only as advisory information, or ignore them entirely?
- Should migration support streaming transfer directly, or only archive-based transfer in the first version?
