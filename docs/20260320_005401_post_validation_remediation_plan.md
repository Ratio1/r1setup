# Post-Validation Remediation Plan

Timestamp: `2026-03-20T00:54:01+02:00`

Source report:

- [20260320_004442_live_integration_report.md](/home/vi/work/ratio1/repos/multi_node_launcher/docs/20260320_004442_live_integration_report.md)

## Goal

Resolve the real-host findings from the live integration run using:

- strong state-model discipline
- backward-compatible rollout
- explicit expert-mode UX
- safe machine/instance identity handling
- clearer operator feedback during long-running flows

Product rule that remains unchanged:

- default mode stays `1 machine = 1 edge node`
- multi-node on one machine remains explicit `expert` behavior only

## Guiding Principles

1. Never infer topology from service names.
2. Never allow the same remote machine endpoint to exist as two unrelated fleet machines in one config.
3. Do not let UI success diverge from persisted state.
4. Prefer explicit operator confirmation for expert-mode and destructive transitions.
5. Progress feedback must make long-running operations feel alive and understandable.
6. Acceptance criteria must be testable, not aspirational.

## Cross-Phase Engineering Rules

These rules apply to Phases 1 through 8.

### Persistence invariants

After any configuration mutation:

- every instance must reference an existing machine
- every machine `instance_names` list must match the reverse instance assignments
- no two machines may share the same normalized endpoint in one config
- every persisted instance must exist in both JSON model state and generated YAML inventory
- no expert-mode instance may be left without resolved runtime identity
- no UI success message may be shown before persisted state is written and revalidated

### Config write transaction semantics

Mutation flows should follow one disciplined path:

1. load persisted state
2. normalize and validate
3. apply mutation to in-memory model
4. validate invariants
5. write JSON and YAML to temporary files
6. atomically replace persisted files
7. reload both files from disk
8. validate invariants again
9. only then report success to the operator

If any step fails:

- do not report success
- leave the last known-good persisted state in place
- emit a clear operator-visible error

### Config repair policy

When invalid or duplicate machine state is detected:

- prefer preview + confirm for lossy or ambiguous repairs
- allow silent auto-repair only for trivial, non-lossy normalization
- always create a backup snapshot before applying non-trivial repair

Examples:

- safe auto-repair:
  - adding missing derived fields
  - normalizing equivalent endpoint forms
- preview + confirm:
  - merging duplicate machine entries that both contain instance assignments

### Operation locking

Before any state-changing operation:

- acquire a per-config lock
- block concurrent mutation flows such as:
  - add/edit/remove node
  - register/repair machine
  - deploy
  - migration execute/rollback/finalize

Read-only flows may remain unlocked, but should detect and mention active mutation when relevant.

### Transition policy

The following transitions must be handled explicitly, not implicitly:

- `standard` machine with one instance -> `expert` machine with multiple instances
- `expert` machine -> remove one instance but keep machine active
- `expert` machine -> remove last instance and retain empty prepared machine
- duplicate/legacy machine entries -> repaired canonical machine entry
- migration source finalized -> prepared empty machine

### Display-unit policy

For capacity display:

- choose one visible unit convention and keep it consistent
- if raw system values are observed in `GiB` but user messaging says `GB`, explain or normalize explicitly
- never present obviously implausible values without sanity filtering

## Phase 1: Repair Machine Identity And Shared-Host Detection

### Objective

Ensure one physical endpoint maps to one canonical machine record in a config.

### Why first

This is the root cause behind the worst expert-mode corruption observed during the live run.

### Scope

- canonicalize machine lookup by normalized endpoint:
  - `ansible_host`
  - `ansible_user`
  - `ansible_port`
- when adding a node, resolve whether the target machine already exists
- if the machine already exists, reuse that machine record instead of creating a second one
- add a migration/repair pass for configs that already contain duplicate machine entries
- define whether repair is:
  - silent normalization
  - preview + confirm merge
  - hard block with operator guidance

### Best-practice design

- keep one authoritative `machine_id`
- treat endpoint matching as a resolver, not as a stored identity substitute
- add one helper in `r1setup` for endpoint normalization and reuse it everywhere
- isolate fleet-model reconciliation logic from menu code
- create backup snapshots before ambiguous repair merges

### UI/UX changes

- if user adds a node on an already known machine, show:
  - existing machine label
  - current topology mode
  - current assigned instances
- never silently create a second machine for the same endpoint

### Likely code areas

- [`r1setup`](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- fleet model / machine lookup helpers already added in prior phases
- config load / normalization path

### Tests

- add or extend:
  - `test_fleet_model.py`
  - `test_machine_grouping.py`
  - `test_machine_registration.py`
  - `test_config_roundtrip.py`
- cover:
  - add-node on existing machine reuses machine record
  - duplicate legacy machine entries normalize correctly
  - grouped views remain stable after normalization
  - ambiguous duplicate-machine repairs require explicit confirmation

### Non-goals

- not redesigning discovery/import in this phase
- not yet introducing expert-mode UX
- not yet changing runtime naming rules

### Acceptance criteria

- adding a node on the same endpoint never creates a second machine record
- configs with duplicate machine entries are either normalized automatically or blocked with a clear repair message
- after repair or add-node reuse, persisted config contains exactly one machine per normalized endpoint
- JSON and YAML remain mutually consistent after repair
- all related tests pass

## Phase 2: Build Explicit Expert-Mode Entry For Multi-Instance On One Machine

### Objective

Make multi-instance deployment an intentional advanced workflow instead of an accidental side effect of adding a node.

### Scope

- branch `Add New Node` into:
  - new machine
  - additional instance on existing machine
- when adding to an existing machine:
  - detect standard vs expert topology
  - if standard and already occupied, require explicit expert-mode confirmation
- show recommended minimum resources:
  - `4 cores`
  - `16 GB RAM`
- allow advanced override only through explicit expert acknowledgement
- explicitly decide what happens to an existing standard machine label and runtime naming base when transitioning to expert mode

### Best-practice design

- model the transition:
  - `standard with 1 instance` -> `expert with N instances`
- store explicit user intent in metadata
- do not hide resource tradeoffs
- keep expert-only controls out of the normal path until needed
- require confirmation before converting a currently running standard machine into expert-managed topology

### UI/UX changes

- present a clear expert-mode explainer:
  - why this is advanced
  - naming/runtime consequences
  - resource recommendation
  - risk of overcommitting a machine
- ask whether to:
  - keep existing runtime names
  - normalize runtime names for multi-instance operation

### Likely code areas

- [`r1setup`](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- runtime naming helpers
- fleet summary / grouped status views

### Tests

- add:
  - `test_expert_mode_planning.py`
  - `test_runtime_naming.py`
  - `test_r1setup_core.py`
- cover:
  - adding a second instance forces expert flow
  - standard mode cannot silently absorb a second instance
  - expert-mode confirmation persists correct topology metadata
  - cancelling expert-mode entry leaves persisted state unchanged

### Non-goals

- not yet deploying the second instance
- not yet implementing discovery/import

### Acceptance criteria

- user cannot accidentally create a multi-instance machine through the standard add-node flow
- second-instance creation always passes through explicit expert-mode acknowledgement
- topology mode is correct in saved state and grouped UI
- declining expert-mode entry produces no persisted partial node or partial machine state

## Phase 3: Fix Runtime Naming Resolution For Shared Machines

### Objective

Ensure new instances on the same machine get safe runtime identities and do not inherit ambiguous single-node defaults.

### Scope

- when expert mode is active, resolve unique:
  - service names
  - container names
  - volume roots
  - metadata paths
  - helper registry entries
- do not leave newly added instances without resolved runtime fields
- detect collisions before save and before deploy
- ensure generated YAML inventory is complete immediately after config mutation, not only after later deploy steps

### Best-practice design

- centralize runtime-name resolution in one place
- make naming deterministic and testable
- treat names like `edge_node2` as opaque if imported, but generate clean unique names for new launcher-managed expert instances

### UI/UX changes

- show resolved runtime names before saving the new instance
- warn if user-selected custom names collide
- display expert instances under one machine in a clearly nested format

### Tests

- extend:
  - `test_runtime_naming.py`
  - `test_inventory_builder.py`
  - `test_dispatcher_helpers.py`
- cover:
  - second instance gets unique names
  - generated inventory contains complete runtime fields
  - dispatcher/helper registration stays collision-free

### Non-goals

- not changing imported preserved runtime identities in this phase
- not yet changing delete/edit persistence logic

### Acceptance criteria

- every expert-mode instance has a complete resolved runtime identity
- same-machine deploy plans never reuse single-instance defaults unless explicitly intended and collision-free
- generated YAML inventory for a newly added expert instance is deploy-ready without missing runtime fields

## Phase 4: Make Remove/Edit Flows Persist Correctly

### Objective

Eliminate the mismatch between visible UI state and persisted config state.

### Scope

- fix remove-node so deletion updates:
  - persisted config JSON
  - persisted inventory YAML
  - fleet machine `instance_names`
  - orphaned machine cleanup where appropriate
- fix edit-node on shared machines so changes apply to the correct instance and machine
- define cleanup rules for:
  - deleting the last instance on a machine
  - deleting one of multiple instances on a machine
- ensure remove/edit paths use the same persistence transaction path as add/repair

### Best-practice design

- one mutation path should own:
  - in-memory state update
  - validation
  - persistence
  - post-save verification
- use transactional thinking:
  - mutate model
  - persist
  - reload/validate
  - only then show success
- do not allow JSON success with YAML failure or YAML success with JSON failure

### UI/UX changes

- success messages should only appear after persistence succeeds
- delete confirmation should mention whether the action removes:
  - only the instance
  - or also an empty machine record

### Tests

- add:
  - `test_instance_operations.py`
  - `test_config_roundtrip.py`
- cover:
  - remove undeployed extra instance on shared machine
  - remove last instance and orphaned machine cleanup
  - edit existing shared-machine instance preserves other instances
  - failed persistence leaves previous state unchanged

### Non-goals

- not yet improving machine spec discovery
- not yet changing migration health semantics

### Acceptance criteria

- if UI says a node was deleted, it is gone from both JSON and YAML state
- machine membership lists remain consistent after remove/edit operations
- failed edit/remove persistence does not leave half-written state on disk

## Phase 5: Fix Machine Spec Discovery And Resource Messaging

### Objective

Make machine-capacity information credible and useful.

### Scope

- fix RAM detection on remote machines
- normalize units carefully:
  - distinguish `GB` vs `GiB`
- decide and document tolerance behavior around `16 GB` class machines that report about `15 GiB`
- add expert-only resource override messaging if still desired
- define one visible display convention for RAM values

### Best-practice design

- separate:
  - raw observed values
  - displayed normalized values
  - policy decisions based on those values
- avoid magic thresholds without explanation
- add sanity checks for implausible values before persistence

### UI/UX changes

- show values in a consistent unit
- if the machine is near the recommended boundary, say so clearly
- avoid showing obviously wrong numbers like `1024 GB` without detection/sanity checks

### Tests

- add:
  - `test_machine_specs.py`
  - `test_expert_mode_planning.py`
- cover:
  - normal Linux RAM parsing
  - sanity rejection of impossible values
  - tolerance messaging near the 16 GB recommendation

### Non-goals

- not enforcing hard scheduling or resource isolation policy in this phase
- not yet redesigning migration UI

### Acceptance criteria

- real hosts in this class display believable RAM values
- expert-mode resource messaging is consistent and understandable
- implausible machine spec values are rejected or flagged before persistence

## Phase 6: Align Migration Health Semantics And Recovery Messaging

### Objective

Make migration outcome reporting truthful and internally consistent.

### Scope

- define exactly what `app_health` means
- ensure successful migration sets health fields consistently
- if app-level health is not yet verified, reflect that explicitly in the CLI and plan state
- add clearer phase summaries during:
  - stop source
  - archive source
  - download local
  - upload target
  - apply target
  - verify target
  - finalize assignment
- define what outcome combinations are valid:
  - runtime healthy, app health unknown
  - runtime healthy, app health verified
  - runtime failed

### Best-practice design

- separate runtime health from app health if both exist
- never report generic success while internal status says unhealthy without explanation

### UI/UX changes

- use clear migration phase markers
- on success, summarize:
  - source stopped
  - archive verified
  - target started
  - assignment updated
  - finalization pending or complete

### Tests

- extend:
  - `test_migration_execution.py`
  - `test_migration_finalization.py`
  - `test_r1setup_core.py`
- cover:
  - success state with correct health fields
  - partial success where runtime is up but app-health is unknown
  - operator-visible messaging for both

### Non-goals

- not redesigning migration transfer architecture
- not changing finalization cleanup policy unless needed for correctness

### Acceptance criteria

- migration status fields and CLI messaging no longer contradict each other
- long-running migration phases show meaningful progress
- successful migration cannot leave an unexplained unhealthy flag in persisted state

## Phase 7: Improve First-Run Timeout And Progress Experience

### Objective

Reduce false failure impressions during fresh-machine operations.

### Scope

- revisit default connection timeout for preparation and first deploy
- optionally use different defaults for:
  - simple status SSH
  - long-running preparation/deploy
- add better output around long-running Ansible subprocesses
- explicitly decide whether default timeout is:
  - global
  - operation-specific
  - adaptive by action type

### Best-practice design

- prefer operation-specific timeout semantics over one global blunt timeout
- give operators safe defaults and a visible escape hatch in settings

### UI/UX changes

- if machine prep may take several minutes, say so up front
- print progress checkpoints when Ansible role boundaries change
- when timing out, offer the likely next action:
  - increase timeout
  - retry machine prep

### Tests

- extend:
  - `test_r1setup_core.py`
  - `test_empty_machine_operations.py`
- cover:
  - timeout setting persistence
  - timeout-specific user guidance text

### Non-goals

- not changing migration semantics in this phase
- not redesigning fleet identity

### Acceptance criteria

- first-run preparation on clean machines no longer feels like a silent hang
- timeout failure guidance is actionable
- long-running operations emit enough progress to distinguish “working” from “stalled”

## Phase 8: Clean Up Message Quality And Screen Redraw Issues

### Objective

Remove avoidable friction from otherwise working workflows.

### Scope

- clean shell-error noise from operator-facing logs where possible
- fix prompt redraw overlap after rollback and similar flows
- normalize machine labels in grouped views
- ensure menu return paths do not redraw beneath stale prompts

### Best-practice design

- user-visible logs should be intentional, not raw leakage
- redraw flow should be deterministic after long-running actions

### Tests

- extend:
  - `test_r1setup_core.py`
  - `test_machine_grouping.py`
- cover:
  - prompt flow after rollback/finalize
  - machine label rendering consistency

### Non-goals

- not changing data model semantics in this phase
- not adding new operational features

### Acceptance criteria

- common flows no longer produce confusing prompt overlap
- grouped machine names are consistent and readable
- operator-facing logs avoid leaking low-signal shell noise during successful paths

## Suggested Delivery Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7
8. Phase 8

Reason:

- phases 1 through 4 address correctness and state integrity
- phases 5 through 8 improve trust, operator understanding, and production polish

## Definition Of Done

This remediation track is complete when:

- same-machine multi-instance creation is explicit, safe, and expert-gated
- no duplicate machine records can be created for the same endpoint
- remove/edit flows persist correctly
- machine specs are credible
- migration status semantics are internally consistent
- first-run operations provide better timeout and progress UX
- the updated flows pass targeted automated tests
- a second real-host validation run confirms the fixes

## Implementation Results

### Phase 1

Status:

- completed

Implemented:

- canonical endpoint normalization for machine identity reuse
- fleet-state canonicalization that collapses duplicate machine records for the same endpoint
- inventory normalization that assigns canonical `r1setup_machine_id` values back onto matching hosts
- add-node reuse hook so newly added hosts bind to an existing machine record when the endpoint already exists

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_fleet_model.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_fleet_model.py)
- [test_config_roundtrip.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_config_roundtrip.py)

Verification:

- `python3 -m unittest tests.test_fleet_model tests.test_config_roundtrip`
- `python3 -m unittest tests.test_machine_grouping tests.test_inventory_builder tests.test_r1setup_core`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- all verification commands passed
- duplicate machine endpoints now collapse to one canonical machine record in fleet metadata
- same-endpoint hosts can now inherit the existing machine id during normalization and add-node flows

### Phase 2

Status:

- completed

Implemented:

- explicit expert-mode gate in `Add New Node` when the target endpoint already belongs to an occupied machine
- in-memory topology promotion helper that converts an existing machine and matching hosts to `expert`
- cancel path that aborts same-machine second-instance creation without saving
- accepted path that marks the new host for expert-mode runtime resolution

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_config_roundtrip.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_config_roundtrip.py)
- [test_r1setup_core.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_r1setup_core.py)

Verification:

- `python3 -m unittest tests.test_config_roundtrip tests.test_r1setup_core`
- `python3 -m unittest tests.test_fleet_model tests.test_machine_grouping tests.test_inventory_builder tests.test_r1setup_core`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- all verification commands passed
- same-machine second-instance add now requires explicit expert-mode confirmation
- declining expert mode leaves configuration state unchanged
- accepting expert mode promotes the existing machine/hosts to expert topology before save

### Phase 3

Status:

- completed

Implemented:

- runtime snapshot persistence helper that writes resolved service/container/volume/metadata fields back onto host config state
- inventory normalization now backfills missing runtime identity for persisted expert-mode hosts
- same-machine add-node flow now persists resolved runtime fields before save
- expert-mode promotion preserves the existing standard runtime identity for already deployed instances before switching topology

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_config_roundtrip.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_config_roundtrip.py)
- [test_r1setup_core.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_r1setup_core.py)

Verification:

- `python3 -m unittest tests.test_config_roundtrip tests.test_r1setup_core`
- `python3 -m unittest tests.test_fleet_model tests.test_machine_grouping tests.test_inventory_builder tests.test_r1setup_core`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- all verification commands passed
- newly added expert-mode instances now persist complete runtime identity immediately
- generated YAML inventory is no longer left with missing runtime fields after same-machine add
- existing standard instances retain their original runtime names when a machine is promoted to expert topology

### Phase 4

Status:

- completed

Implemented:

- fleet-state merge now prunes stale instance records that no longer exist in inventory while retaining empty machine records
- new host-preparation helper preserves machine binding, topology, resource, and runtime metadata across edit flows before save
- delete flow now updates in-memory fleet state before save and keeps last-instance machines as prepared instead of silently leaving stale active metadata
- configuration and metadata writes now use atomic temp-file replacement instead of direct in-place writes

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_config_roundtrip.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_config_roundtrip.py)
- [test_instance_operations.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_instance_operations.py)

Verification:

- `python3 -m unittest tests.test_config_roundtrip tests.test_instance_operations`
- `python3 -m unittest tests.test_r1setup_core tests.test_machine_grouping tests.test_inventory_builder tests.test_fleet_model`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- all verification commands passed
- delete operations now remove instances from both YAML and persisted fleet metadata
- last-instance deletion keeps the machine record and marks it prepared instead of leaving stale active state
- edit flows no longer drop shared-machine identity or runtime fields during persistence

### Phase 5

Status:

- completed

Implemented:

- machine-spec probing now uses remote Python sysconf values and stores fractional GiB instead of lossy integer shell parsing
- machine-spec display now uses explicit `GiB RAM` wording to match the observed unit
- added recommendation assessment for:
  - meets recommendation
  - tolerated near-boundary machines around the nominal 16 GiB class
  - below-recommendation capacity
- registration and expert-mode entry now surface measured machine capacity and the recommendation result directly to the operator

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_machine_specs.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_specs.py)
- [test_machine_grouping.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_grouping.py)

Verification:

- `python3 -m unittest tests.test_machine_specs tests.test_machine_grouping tests.test_r1setup_core tests.test_instance_operations tests.test_config_roundtrip`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- all verification commands passed
- machine spec summaries now use consistent GiB wording
- near-16 GiB machines are messaged as tolerated boundary cases rather than looking like hard failures
- expert-mode prompts now surface observed capacity for the actual machine before confirmation

### Phase 6

Status:

- completed

Implemented:

- migration verification now separates:
  - runtime health
  - app health
  - app-health unknown state
- explicit app-probe failure is now treated as a verification error instead of being flattened into a misleading boolean
- successful migration execution now persists `runtime_health` and `app_health_status` in plan state
- long-running migration execution now prints visible step markers for each major phase
- success messaging now summarizes what was verified instead of only printing a generic completion line

Files changed:

- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [test_migration_execution.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_migration_execution.py)

Verification:

- `python3 -m unittest tests.test_migration_execution tests.test_migration_finalization tests.test_migration_planning`
- `python3 -m unittest tests.test_r1setup_core tests.test_machine_specs tests.test_instance_operations`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Result:

- all verification commands passed
- successful migrations no longer need to persist a contradictory false app-health flag when runtime is verified but app-level confirmation is unavailable
- migration progress is now operator-visible phase by phase
- explicit app-probe failures now stop the migration instead of being silently reported as generic success

## Phase 9: Real-Host Revalidation

### Objective

Verify that the remediations actually fix the real operator problems observed in production-like conditions.

### Scope

- rerun the live-host scenarios from the original integration report
- explicitly rerun:
  - standard deploy
  - empty-machine prep
  - migration planning
  - successful migration
  - finalization
  - interrupted migration with rollback
  - add second instance on same machine
  - edit/remove shared-machine instance flows

### Best-practice design

- use the same kind of real-host protocol that found the current issues
- compare observed behavior against the original report, not just against local expectations

### Tests

- no new unit tests required by this phase itself
- use:
  - real-host checklist
  - integration protocol
  - before/after issue comparison

### Acceptance criteria

- previously reproduced critical issues are no longer reproducible
- expert-mode entry is explicit and safe
- same-machine add/edit/remove flows are stable
- standard-mode workflows remain backward compatible
- a follow-up dated validation report is produced

## Recommended Next Step

Start with Phase 1 and Phase 2 together if implemented carefully, because they form one operator-facing transition:

- identify an existing machine correctly
- then decide whether the user is adding a normal new host or entering expert-mode on that machine
