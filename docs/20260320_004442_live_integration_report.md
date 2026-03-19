# Live Integration Report

Timestamp: `2026-03-20T00:44:42+02:00`

## Scope

This report summarizes a real-host integration run of the repo-local `r1setup` workflow against:

- `35.228.69.214` (`r1-vi-g1`)
- `34.88.90.109` (`r1-vi-g2`)

SSH user:

- `vitalii`

Test intent:

- validate standard single-node behavior
- validate registered empty-machine preparation
- validate migration planning
- validate successful migration execution
- validate migration finalization
- validate interrupted migration rollback
- assess operator UX and workflow clarity
- probe the advanced multi-node-on-one-machine path from a real user perspective

## Test Environment

Initial remote state:

- both machines were clean: no `edge_node*` systemd units, no Docker containers
- both machines were Ubuntu `24.04.4`
- both machines allowed passwordless `sudo`
- both machines had `4` CPU and about `15 GiB` RAM
- neither machine had Docker installed initially

Local execution mode:

- repo-local `r1setup`
- repo-local Ansible collection
- isolated dev home under `/tmp/r1setup-dev`
- real SSH keys reused from local `~/.ssh`

## Scenarios Executed

### 1. Machine inspection and baseline

Result: `PASS`

Observed:

- both machines were suitable for clean install testing
- no pre-existing `edge_node` runtime state needed cleanup

### 2. Register empty machine

Result: `PASS with issues`

Observed:

- `34.88.90.109` was registered as `machineb`
- machine preparation completed successfully later

Issues:

- machine spec probe reported `4 CPU / 1024 GB RAM` on `34.88.90.109`
- that value was persisted and shown in UI

### 3. Prepare registered machine without deployment

Result: `PASS after operator workaround`

Observed:

- the first attempt timed out with the default timeout
- after increasing `Connection Timeout` to `600s`, preparation succeeded
- Docker was installed and active on `34.88.90.109`

Issues:

- default `30s` timeout is too low for first-time prep on clean machines
- the failure message is technically correct but does not guide the user toward the likely fix

### 4. Standard single-node deployment

Result: `PASS`

Observed:

- deployed `nodea` to `35.228.69.214`
- resulting runtime:
  - service: `edge_node.service`
  - container: `edge_node`
  - mount: `/var/cache/edge_node/_local_cache -> /edge_node/_local_cache`
- service reached `active`
- container reached `running`

### 5. Migration planning

Result: `PASS`

Observed:

- plan from `35.228.69.214` to `machineb` created successfully
- transfer route was clearly shown:
  - `source -> local temp -> target`
- plan persisted in config metadata
- preflight correctly showed volume size and free-space checks

Positive note:

- this was one of the clearest parts of the workflow

### 6. Successful migration execution

Result: `PASS with issues`

Observed:

- source service stopped correctly
- archive created on source
- archive downloaded to local temp
- archive uploaded to target
- target runtime applied and started
- assignment updated to target machine
- target machine became active and source machine retained deferred cleanup state

Issues:

- `migration_plan_state.app_health` remained `false` even though migration was reported as successful
- operator-facing output was too quiet during long-running phases

### 7. Migration finalization

Result: `PASS`

Observed:

- finalized successful migration without removing source volume data
- source archive removed
- target archive removed
- local archive removed
- source service/unit removed
- source volume retained as expected

### 8. Forced interrupted migration and rollback

Result: `PASS`

Observed:

- planned reverse migration back to `35.228.69.214`
- interrupted execution after the source had been stopped and archive transfer had begun
- saved plan remained in `executing` state with `last_step = archive_downloaded`
- rollback restarted the source runtime on `34.88.90.109`
- rollback cleaned local and remote archive artifacts
- rollback left target machine clean and without recreated service/unit

Positive note:

- this is an important success case; the rollback path worked on real machines, not only in tests

### 9. Advanced-user multi-node-on-one-machine probe

Result: `FAIL`

Observed:

- added `nodeb` pointing to the same host as `nodea` (`34.88.90.109`)
- the UI allowed this without explicit expert-mode confirmation
- the workflow did not warn about shared-machine topology, resource limits, or runtime-name conflicts

Persisted-state problems discovered:

- a second machine record was created for the same host:
  - existing: `machineb`
  - new duplicate: `vitalii@34.88.90.109:22`
- both duplicate machine records remained in `standard` mode
- `nodeb` had no resolved runtime identity in the generated YAML inventory

Remove flow problems discovered:

- UI reported `nodeb` deleted successfully
- visible node list returned to one node
- persisted config still retained `nodeb`
- persisted config still retained the duplicate machine record

Conclusion:

- advanced multi-instance behavior is not release-ready

## Confirmed Technical Bugs

### Critical

1. Multi-node add flow can create duplicate machine identities for the same endpoint.

Impact:

- corrupt fleet model
- breaks machine grouping semantics
- undermines expert-mode architecture

Observed state:

- `machineb`
- `vitalii@34.88.90.109:22`

Both pointed to the same machine.

2. Multi-node add flow does not force or even acknowledge expert mode.

Impact:

- users can accidentally enter a multi-instance scenario while still in `standard`
- runtime naming/resource assumptions are not surfaced

3. Remove-node flow is not persisting deletion consistently.

Impact:

- UI says a node was deleted
- persisted config still keeps it
- user trust and state integrity are both harmed

### High

4. Machine spec probing returned `1024 GB RAM` for a host with about `15 GiB`.

Impact:

- wrong capacity display
- wrong migration-planning context
- future resource validation logic would be unreliable

5. Successful migration leaves `migration_plan_state.app_health = false`.

Impact:

- success criteria are internally inconsistent
- later reporting/automation may misclassify a good migration

6. Default `30s` timeout is too low for clean-host preparation.

Impact:

- normal first-time users can fail before installation actually finishes

### Medium

7. Stop-service log output includes shell error noise:

- `/bin/sh: 1: [: Illegal number:`

Impact:

- looks like migration failure even when stop succeeds

8. Long-running deployment/migration phases provide too little progress feedback.

Impact:

- operator may assume the tool is hung

## UX / Workflow Issues

1. Machine naming is inconsistent.

Examples:

- friendly registered label: `machineb`
- raw derived identifier: `vitalii@35.228.69.214:22`

Impact:

- grouped fleet views look uneven
- users have to mentally map two naming systems

2. Bulk-selection defaults feel too aggressive.

Examples:

- deploy host selection starts with everything selected
- prepare-machine selection starts with all selected

Impact:

- efficient for small configs
- risky/confusing for larger fleets

3. Multi-instance entry point is not explicit enough.

Observed behavior:

- adding a second node on the same machine feels identical to adding a node on a new host

Expected behavior:

- clear branch:
  - new machine
  - additional instance on existing machine
- explicit expert-mode acknowledgement

4. Migration success messaging is too compressed relative to the amount of work done.

Observed:

- final success line is short
- long silent intervals happen before it

Expected:

- clearer phase progress or summarized milestones

5. Rollback screen redraw is slightly broken.

Observed:

- `Press Enter to continue...` remained visible while the deployment menu was already redrawn underneath it

## Final Remote State

### `34.88.90.109` (`r1-vi-g2`)

Current state:

- `edge_node.service`: `enabled`, `active`
- running container:
  - `edge_node`
- active mount:
  - `/var/cache/edge_node/_local_cache -> /edge_node/_local_cache`

This is the current active node host at the end of the test run.

### `35.228.69.214` (`r1-vi-g1`)

Current state:

- no `edge_node` unit file present
- no running `edge_node` container
- machine remains Docker-prepared

This machine is effectively back to a prepared empty-machine state.

## Operation Log Observations

The local operation log exists at:

- `/tmp/r1setup-dev/.ratio1/r1_setup/logs/operations.log`

Validated entries:

- migration execution `started`
- migration execution `success`
- migration finalization `started`
- migration finalization `success`
- interrupted reverse migration execution `started`
- rollback `started`
- rollback `success`

This is useful and should be kept, but later improvements should include:

- clearer per-phase outcome detail
- explicit failure entries for interrupted/cancelled operations
- easier correlation between CLI-visible actions and log records

## Release Readiness Assessment

### Standard mode

Status: `mostly good, but needs polish`

Reason:

- deployment, migration, finalization, and rollback all worked on real hosts
- timeout default and progress visibility still need improvement

### Expert mode / multiple nodes on one machine

Status: `not ready`

Reason:

- adding a second node on the same host currently produces invalid or inconsistent topology state
- delete cleanup is not trustworthy in that scenario

## Recommended Fix Order

1. Fix same-machine node addition so endpoint deduplication, topology transition, and machine identity reuse work correctly.
2. Fix remove-node persistence so UI success matches saved state.
3. Fix machine spec probing, especially RAM detection.
4. Define and enforce the explicit expert-mode branch for multi-instance flows.
5. Align migration success criteria with `app_health`.
6. Improve default timeout behavior and first-time-prep guidance.
7. Improve progress reporting for long-running deploy/migration phases.
8. Normalize machine naming in grouped views and menus.

## Bottom Line

The real-host run validates the core standard deployment and migration architecture. The migration path, including rollback after interruption, is materially working.

The major remaining risk is the operator-facing multi-instance path. Right now it is too easy to enter it accidentally, and the resulting persisted state is inconsistent. That needs to be fixed before expert-mode support can be considered reliable.
