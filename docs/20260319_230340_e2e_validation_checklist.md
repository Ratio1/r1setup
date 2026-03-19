# r1setup E2E Validation Checklist

Created At: `2026-03-19T23:03:40+02:00`

## Goal

Validate the full operator workflow on real machines before wider release.

This checklist covers:

- standard mode: `1 machine = 1 edge node`
- expert mode: multiple edge nodes on one machine
- empty-machine registration and preparation
- migration planning and execution
- rollback after failure
- finalization after success

## Test Modes

Use one of these test approaches:

1. Repo-local dev workflow against real configs:
```bash
bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh --use-real-configs
```

2. Repo-local dev workflow against isolated dev configs:
```bash
bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh
```

## Test Bed

Prepare at least these machines:

- Machine A: source machine with one working edge node
- Machine B: empty target machine for migration
- Machine C: expert-mode machine for multiple instances on one host

Recommended coverage:

- at least one GPU-capable host
- at least one CPU-only deploy path
- at least one host reachable with the exact SSH method real users use

## Preconditions

Before starting:

- confirm you can SSH to all test machines
- confirm disk space is available on:
  - machine A source volume filesystem
  - machine B target volume filesystem
  - local controller temp filesystem
- confirm Docker/systemd are usable on target machines
- confirm you know which config you are testing
- confirm you are not testing on production-critical nodes

Record these before the run:

- CLI commit under test
- collection source under test
- active config name
- environment under test: `mainnet`, `testnet`, or `devnet`
- machine IDs, IPs, and expected service names

## Global Pass Criteria

The release candidate should satisfy all of these:

- existing standard-mode configs still behave as single-machine single-node
- expert-mode machines render grouped instance views correctly
- empty machines can be registered and prepared without fake node entries
- migration uses `source -> local temp -> target`
- assignment changes only after verified target success
- rollback restores source availability without manual config edits
- finalization does not happen implicitly
- no machine-global helper/script collision occurs in expert mode
- no config corruption occurs after repeated operations

## Phase A: Standard Mode Baseline

Objective:
- prove backward-compatible `standard` behavior still works

Steps:
1. Open `r1setup`.
2. Load or create a standard config with one machine and one node.
3. Check `Fleet Summary`.
4. Check `Node Status & Info`.
5. Run deploy if not already deployed.
6. Run:
   - start
   - stop
   - restart
   - update service file
7. Re-open status views after each action.

Verify:

- the machine displays as one machine with one instance
- helper behavior remains standard-mode behavior
- service/container/volume names are stable
- no expert-mode dispatcher requirement appears
- service file update still works normally

Pass if:

- all standard operations work without expert-mode prompts
- grouped UI remains concise for standard topology

## Phase B: Empty Machine Registration

Objective:
- prove a machine can exist in fleet state without a node

Steps:
1. Register Machine B from `Configuration Menu`.
2. Choose `standard` topology.
3. Do not deploy a node.
4. Open `Fleet Summary`.
5. Open `Deployment Menu -> Prepare Machines`.
6. Prepare Machine B.
7. Open `Fleet Summary` again.

Verify:

- Machine B appears before deployment
- it shows as empty/registered before preparation
- after preparation it shows as prepared
- no placeholder instance appears
- no unexpected inventory host entry is created

Pass if:

- machine-only preparation succeeds and fleet state is correct

## Phase C: Expert Mode Multi-Instance On One Machine

Objective:
- prove multiple services can be managed on one machine without collisions

Steps:
1. Register or use Machine C as `expert`.
2. Configure two logical instances assigned to Machine C.
3. Deploy both instances.
4. Open `Fleet Summary`.
5. Open `Node Status & Info`.
6. Edit one instance configuration while leaving the sibling instance unchanged.
7. Run operations separately on each instance:
   - stop instance 1
   - keep instance 2 running
   - restart instance 2
8. Remove one instance from the config or delete one disposable deployment while leaving the other instance present.
9. Check remote service names, container names, and volume paths.

Verify:

- Machine C is shown once with two nested instances
- per-instance service names are distinct
- per-instance container names are distinct
- per-instance volume paths are distinct
- `r1service` dispatcher behavior works for expert mode
- operating on one instance does not affect the other
- editing one instance does not silently rewrite the sibling instance runtime
- removing one instance does not remove the surviving instance or shared machine preparation unexpectedly

Pass if:

- both instances are independently manageable on one machine
- no helper/script collisions occur
- add/edit/remove lifecycle remains correct for expert mode

## Phase D: Migration Planning

Objective:
- prove planning is non-mutating and accurate

Steps:
1. Ensure node `X` is running on Machine A.
2. Ensure Machine B is registered and ideally prepared.
3. Open `Deployment Menu -> Plan Migration`.
4. Select node `X`.
5. Select Machine B.
6. Test at least:
   - `preserve`
   - `normalize_to_target`
7. Save the plan.

Verify:

- the plan shows:
  - source machine
  - target machine
  - resolved runtime names
  - transfer route through local temp
- source service is still running
- target machine was not modified by planning
- assignment is unchanged

Pass if:

- planning saves a correct plan without mutating either machine

## Phase E: Successful Migration Execution

Objective:
- prove end-to-end migration success

Steps:
1. Start from a saved `planned` migration.
2. Run `Deployment Menu -> Execute Migration`.
3. Observe status until completion.
4. After success, inspect:
   - `Fleet Summary`
   - `Node Status & Info`
   - source machine
   - local temp folder
   - target machine

Verify:

- Machine B is prepared before transfer if needed
- source service stops before archive creation
- archive exists locally during transfer
- target archive checksum matches source/local
- target service starts successfully
- node health verification passes
- assignment moves to Machine B only after verification
- source cleanup has not yet occurred
- local temp artifact still exists before finalization

Pass if:

- the instance is running on Machine B
- fleet/config assignment points to Machine B
- source artifacts remain available for cleanup or rollback follow-up

## Phase F: Forced Failure And Rollback

Objective:
- prove failure recovery is safe

Use one failure-injection method:

- make target startup fail after transfer
- break target permissions deliberately
- make target verification fail

Recommended method:

- alter target runtime or temporarily break target service startup after planning and before successful verification

Steps:
1. Create a fresh migration plan from Machine A to Machine B.
2. Force a target-side failure.
3. Execute migration and let it fail.
4. Confirm plan status becomes failure-related.
5. Run `Deployment Menu -> Rollback Migration`.
6. Re-check:
   - source machine
   - target machine
   - local temp folder
   - `Fleet Summary`
   - `Node Status & Info`

Verify:

- assignment remains source-authoritative
- source runtime is restarted by rollback
- target partial runtime is cleaned conservatively
- local archive is removed during rollback
- remote archives are removed during rollback
- plan status reflects rolled-back state

Pass if:

- source node is running again without manual config repair
- target no longer holds the partial migrated runtime

## Phase G: Successful Finalization

Objective:
- prove explicit post-success cleanup works

Steps:
1. Start from a successfully executed migration.
2. Do not roll back.
3. Run `Deployment Menu -> Finalize Migration`.
4. Test twice if possible:
   - once without removing source volume data
   - once with source volume removal on a disposable run

Verify:

- source service artifacts are removed
- source archive is removed
- target archive is removed
- local temp archive is removed
- optional source volume removal only happens when explicitly confirmed
- target runtime remains healthy after finalization
- plan status becomes finalized

Pass if:

- finalization performs only explicit cleanup and does not disturb the target runtime

## Phase H: Reopen And Recheck State

Objective:
- ensure state survives a fresh CLI session

Steps:
1. Exit `r1setup`.
2. Re-open `r1setup`.
3. Load the same config.
4. Re-open:
   - `Fleet Summary`
   - `Node Status & Info`
   - `Deployment Menu`

Verify:

- topology, machine assignments, and migration state are still consistent
- standard vs expert behavior is still correct
- no duplicate instances appear
- no stale migration state blocks unrelated operations incorrectly

Pass if:

- persisted state remains coherent across CLI restarts

## Phase I: Regression Safety

Objective:
- ensure unrelated operator workflows still work after all above scenarios

Run these checks:

- update service file on a non-migrating node
- stream logs for:
  - standard instance
  - expert instance
- `get_node_info` for:
  - standard instance
  - expert instance
- delete deployment on a disposable node
- switch configs and come back

Verify:

- helper commands still map correctly
- grouped views remain correct
- config switching does not lose fleet metadata
- standard mode remains default and unaffected

## Artifacts To Capture

For each scenario, capture:

- screenshots or terminal output of the relevant menu state
- saved migration plan status before and after operation
- source and target service names
- source and target volume paths
- operation-log entries from the local operation log
- any error message verbatim

## Recommended Real-Host Matrix

Minimum matrix:

1. Standard deploy on one host
2. Expert dual-instance deploy on one host
3. Empty-machine prepare
4. Migration success A -> B
5. Migration failure A -> B followed by rollback
6. Migration success A -> B followed by finalization

Useful extra matrix:

1. `preserve` naming migration
2. `normalize_to_target` migration
3. root SSH host
4. non-root with sudo host
5. GPU machine
6. CPU-only machine
7. expert machine with add/edit/remove of one instance while another stays live

## Exit Criteria For Public Release

Do not treat the feature as production-ready until:

- every minimum-matrix scenario passes
- at least one forced-failure rollback passes
- at least one finalization-without-volume-removal passes
- at least one finalization-with-volume-removal passes on disposable data
- no config corruption is observed after repeated reopen/reload
- operation logs are present and readable
- no expert-mode behavior leaks into standard-mode workflows

## Follow-Up If Any Test Fails

For each failure, record:

- scenario name
- exact step number
- actual result
- expected result
- saved migration plan status
- whether assignment changed
- whether source runtime remained recoverable
- whether temp artifacts remained unexpectedly

Do not continue to finalization testing on a broken migration-execution build.
