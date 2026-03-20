## Remaining Implementation Plan

Timestamp: `2026-03-20T10:19:02+02:00`

This plan covers the remaining post-core work:

1. selective discovery/import of existing remote `edge_node` services
2. repair/migration handling for old pre-fix `rollback_failed` saved plans
3. release-prep hardening and final validation

The product rule remains unchanged:

- `standard` mode is the default: `1 machine = 1 edge node`
- `expert` mode is explicit and required for multiple nodes on one machine

## Scope

In scope:

- operator-visible discovery flow
- safe selective import into the current config
- cross-config conflict detection
- legacy migration-plan repair
- release gating, docs, and final validation

Out of scope:

- automatic import without user review
- silent topology inference from service names
- broad redesign of the completed migration engine

## Cross-Phase Rules

- Discovery must be read-only until the user explicitly confirms import.
- Imported services must preserve discovered runtime names by default.
- Service names like `edge_node2` or `edge_node3` must never by themselves imply expert mode.
- Config persistence must stay transactional:
  - mutate in memory
  - validate invariants
  - write temp files
  - atomically replace saved files
  - reload and revalidate
- New coverage should stay modular in `mnl_factory/scripts/tests/`.

## Phase 1: Discovery Scan And Candidate Model

Objective:
- Scan a selected registered machine for existing edge-node-like services and normalize the results into import candidates.

Implementation:
- Add a discovery candidate data model in `r1setup`.
- Add a remote scan path that inspects:
  - systemd unit files and unit state
  - service content and rendered environment
  - Docker container names and mounts
  - launcher metadata when present
- Infer environment with precedence:
  - launcher metadata
  - service file / environment
  - image tag
  - otherwise `unknown`
- Mark confidence/source for inferred environment.
- Do not mutate remote state.

Likely code areas:
- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- possible helper playbook under [playbooks](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/playbooks)

Tests:
- `test_discovery_scan.py`
- `test_discovery_inference.py`
- `test_discovery_ui_rendering.py`

Acceptance criteria:
- discovery on a machine returns zero or more normalized candidates
- discovery performs no remote mutation
- candidates include service name, runtime identity, mounts, detected environment, and detection source when available
- a service named `edge_node2` on an otherwise single-node machine is still just a candidate, not an auto-expert conversion

Non-goals:
- importing candidates
- editing discovered services

## Phase 2: Selective Import Into Current Config

Objective:
- Let the user choose exactly which discovered services to add to the current config.

Implementation:
- Add `Discover Existing Services` on registered machines.
- Show candidates in a review screen with multi-select import.
- Preserve runtime names on import by default:
  - service name
  - container name
  - volume path
- Add imported instances with explicit metadata such as:
  - `imported_from_discovery = true`
  - `runtime_name_policy = preserve`
- Detect duplicate ownership across configs using normalized `(machine endpoint + service name)`.
- If multiple imported instances on one machine are selected into the same config, require explicit expert-mode confirmation.
- If one candidate is imported, default to standard unless the user chooses expert explicitly.

Likely code areas:
- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [README_r1setup.md](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/README_r1setup.md)

Tests:
- `test_discovery_import_plan.py`
- `test_discovery_duplicates.py`
- `test_discovery_config_roundtrip.py`

Acceptance criteria:
- the user can import any subset of discovered candidates into the current config
- unselected candidates are left untouched
- imported instances persist correctly in both config metadata and generated inventory
- importing a candidate already tracked by another config produces an explicit warning/confirmation path
- importing one service from a host that also runs other services does not force those others into the config

Non-goals:
- auto-merging imported services into multiple configs
- renaming preserved runtime identities during import

## Phase 3: Discovery-Aware UX And Status Integration

Objective:
- Make discovery/import understandable and consistent in the grouped machine UX.

Implementation:
- Show registered machines as one of:
  - empty / no discovered services
  - discovered services not imported
  - imported tracked instances
- Add concise wording that distinguishes:
  - discovered but unmanaged
  - tracked but undeployed
  - tracked and running
- Add follow-up prompt after machine registration:
  - offer discovery
  - do not force it
- Make environment mismatches explicit:
  - current config environment vs discovered environment
  - warn before import when they differ

Likely code areas:
- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- [README_r1setup.md](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/README_r1setup.md)

Tests:
- extend `test_machine_grouping.py`
- extend `test_r1setup_core.py`
- `test_discovery_ui_rendering.py`

Acceptance criteria:
- grouped views clearly distinguish discovered-but-untracked services from imported tracked instances
- registration flow can offer discovery without forcing import
- environment mismatch warnings are visible and understandable
- standard-mode UX remains simple for users who never use discovery

Non-goals:
- deep service editing from the discovery screen

## Phase 4: Legacy Migration Plan Repair

Objective:
- Repair saved pre-fix migration plans that were left in stale `rollback_failed` states even though the source node is healthy again.

Implementation:
- Add a one-time repair/normalization path on load for stale plan states.
- Repair only when the state is unambiguous, for example:
  - saved status is `rollback_failed`
  - source assignment still points to the original machine
  - source runtime verifies healthy
- Record repair in operation log and plan metadata.
- If the state is ambiguous, keep it visible and require operator action instead of guessing.

Likely code areas:
- [r1setup](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)

Tests:
- `test_migration_plan_repair.py`
- extend `test_migration_finalization.py`

Acceptance criteria:
- clearly recoverable old plans are normalized automatically or through one explicit repair prompt
- ambiguous legacy states are not silently rewritten
- repaired plans stop showing a stale failure state in the UI

Non-goals:
- redesigning migration execution

## Phase 5: Release Prep And Documentation Pass

Objective:
- Make the implemented feature set releasable and understandable.

Implementation:
- Update operator docs for:
  - expert mode
  - empty machine registration
  - migration workflow
  - discovery/import workflow
  - known limits and safety rules
- Review release-sensitive surfaces:
  - `ver.py` / fallback `CLI_VERSION`
  - `galaxy.yml` if collection release is intended
  - user-visible menu wording
  - changelog/release notes source doc if needed
- Verify AGENTS durable notes only if a stable repo convention changed materially.

Likely code areas:
- [README_r1setup.md](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/README_r1setup.md)
- [AGENTS.md](/home/vi/work/ratio1/repos/multi_node_launcher/AGENTS.md)
- release/version files as needed

Tests:
- full `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`
- targeted smoke tests for startup/version messaging if changed

Acceptance criteria:
- operator docs match the shipped workflows
- no known menu wording contradicts actual behavior
- version sources remain aligned if bumped

Non-goals:
- new feature development beyond discovery/import and plan repair

## Phase 6: Final Live Validation And Release Gate

Objective:
- Re-run the highest-risk real-host flows after the remaining work lands.

Validation matrix:
- standard single-node deploy path
- empty-machine registration and optional discovery
- selective import of one service from a machine with multiple candidates
- expert-mode same-machine multi-instance flow
- migration plan / execute / rollback / finalize
- startup/status UX sanity check

Acceptance criteria:
- no config corruption across YAML + metadata
- no false running-state attribution across sibling instances
- no stale migration-failure state after successful recovery
- selective import behaves exactly as chosen by the user
- live UX is understandable without needing internal implementation knowledge

## Recommended Delivery Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6

## Suggested Commit Strategy

- one commit per phase
- update this file after each phase with an `Implementation Results` subsection
- run targeted tests for the phase plus full suite before each phase commit

## Implementation Results

### Phase 1

Status:
- completed on `2026-03-20`

What landed:
- added a real non-mutating discovery scan API in [`r1setup`](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- added environment inference precedence:
  - metadata
  - service environment
  - image tag
  - `unknown`
- added normalized discovery candidate output including:
  - service identity
  - container identity/state
  - configured/live/effective mounts
  - detected environment with source/confidence
  - service file version
  - `managed_by_r1setup`
- kept discovery read-only; no import or remote mutation was added in this phase

Tests added:
- [test_discovery_inference.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_discovery_inference.py)
- [test_discovery_scan.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_discovery_scan.py)

Verification:
- `python3 -m unittest tests.test_discovery_inference tests.test_discovery_scan`
- `python3 -m unittest tests.test_machine_specs tests.test_r1setup_core`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Results:
- `224` tests passed
- `py_compile` passed

Follow-up for next phase:
- wire this backend into a selective import review flow without auto-mutating config or remote state

### Phase 2

Status:
- completed on `2026-03-20`

What landed:
- added cross-config runtime-identity claim lookup for discovery warnings
- added a selective discovery-import workflow in [`r1setup`](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/r1setup)
- added `Configuration -> Discover Services`
- import now:
  - scans one selected registered machine
  - shows discovered candidates
  - lets the user choose a subset explicitly
  - warns on environment mismatch
  - warns when another saved config already tracks the same `(machine endpoint + service name)`
  - preserves discovered runtime identities by default
  - promotes the target machine to expert mode only when the resulting tracked instance count requires it
- imported instances now persist discovery-import metadata in fleet state

Tests added:
- [test_discovery_import_plan.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_discovery_import_plan.py)
- [test_discovery_duplicates.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_discovery_duplicates.py)

Verification:
- `python3 -m unittest tests.test_discovery_import_plan tests.test_discovery_duplicates tests.test_discovery_scan tests.test_discovery_inference`
- `python3 -m unittest tests.test_machine_registration tests.test_inventory_builder tests.test_r1setup_core`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Results:
- `227` tests passed
- `py_compile` passed

Follow-up for next phase:
- make grouped machine/status views distinguish discovered-untracked vs imported-tracked services more clearly

### Phase 3

Status:
- completed on `2026-03-20`

What landed:
- persisted the latest machine discovery scan results in fleet-state machine metadata
- grouped machine views now surface untracked discovered services separately from imported tracked instances
- grouped CLI display now renders:
  - assigned instances in the current config
  - discovered services on the same machine that were not imported into the current config
- machine registration now offers a follow-up discovery step instead of forcing the user to find it later

Tests extended:
- [test_machine_grouping.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_grouping.py)
- [test_machine_registration.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_registration.py)
- [test_machine_specs.py](/home/vi/work/ratio1/repos/multi_node_launcher/mnl_factory/scripts/tests/test_machine_specs.py)

Verification:
- `python3 -m unittest tests.test_machine_grouping tests.test_machine_registration tests.test_discovery_import_plan`
- `python3 -m unittest tests.test_machine_grouping tests.test_machine_registration tests.test_discovery_import_plan tests.test_r1setup_core`
- `python3 -m unittest tests.test_machine_specs tests.test_machine_registration tests.test_machine_grouping`
- `python3 -m unittest discover tests`
- `python3 -m py_compile r1setup`

Results:
- `230` tests passed
- `py_compile` passed

Follow-up for next phase:
- add one-time repair/normalization for clearly recoverable legacy `rollback_failed` migration plans
