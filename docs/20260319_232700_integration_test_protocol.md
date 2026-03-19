# r1setup Remote Integration Test Protocol

Created At: `2026-03-19T23:27:00+02:00`

## Purpose

Define how to run full remote integration testing against real machines and how to capture:

- functional failures
- migration/rollback/finalization issues
- UX/UI problems
- confusing operator flows
- wording/menu inconsistencies

This document is the execution protocol for live-host validation after the local automated suite.

## Test Objective

When you provide remote machine access, the test effort should answer these questions:

1. Does the feature work correctly on real hosts?
2. Does it remain backward compatible for standard users?
3. Are expert-mode flows understandable enough for advanced users?
4. Are migration, rollback, and finalization safe and comprehensible?
5. What UX/UI issues would a real operator hit even if the backend technically works?

## Testing Mode

The test should be run in two roles at once:

1. Technical validator
   - check remote correctness
   - verify services, volumes, state transitions, inventories, and cleanup

2. Simulated operator
   - use the CLI as a real user would
   - note confusion, ambiguity, poor defaults, unclear warnings, weak status wording, and bad menu placement

## Required Inputs Before Test Start

Before starting a live integration session, collect:

- repo commit under test
- whether we are using:
  - installed `r1setup`
  - repo-local dev runner
- config source:
  - real configs
  - isolated dev configs
- environment under test:
  - `mainnet`
  - `testnet`
  - `devnet`
- remote machine list with labels
- expected role of each machine:
  - standard machine
  - empty target machine
  - expert-mode machine
  - migration source
  - migration target
- SSH auth mode per machine
- whether data is disposable

## Required Machine Set

Minimum recommended set:

- Machine A: standard deployed node, migration source
- Machine B: empty registered machine, migration target
- Machine C: expert-mode multi-instance machine

Useful extra hosts:

- one non-root sudo machine
- one CPU-only host
- one host with pre-existing nonstandard service naming

## Session Rules

During live testing:

- do not skip status verification between major actions
- do not assume a flow is good just because Ansible succeeds
- after every major step, inspect both:
  - CLI-visible state
  - remote actual state
- record confusion even when there is no bug
- prefer proving behavior over assuming behavior

## Test Scenario Set

The live session should cover all of these.

### Scenario 1: Standard Existing User Baseline

Goal:
- prove that a normal user still experiences `1 machine = 1 node`

Run:

1. load an existing standard config
2. inspect `Fleet Summary`
3. inspect `Node Status & Info`
4. run one normal operation:
   - restart
   - update service file
   - logs
5. inspect status again

Check:

- no expert-mode language appears unnecessarily
- the grouped display is still simple
- commands still behave like a normal single-node workflow

### Scenario 2: Register Empty Machine

Goal:
- prove machine-only onboarding works

Run:

1. register a new machine without deploying a node
2. inspect grouped views
3. prepare the machine
4. inspect grouped views again

Check:

- machine appears without fake instance rows
- machine state changes are understandable
- menu wording makes it clear that prepare is not deploy

### Scenario 3: Expert Multi-Instance Machine

Goal:
- prove multiple services on one machine are manageable

Run:

1. open config with expert-mode machine
2. add a second logical node to the same physical machine if not already present
3. inspect grouped status
4. edit one instance while leaving the sibling instance unchanged
5. operate on one instance only
6. remove or delete one disposable instance while keeping the other one
7. inspect remote services/containers/volumes
8. confirm the second instance is unaffected

Check:

- UI clearly shows one machine with multiple nodes
- per-instance names are visible enough
- the dispatcher/helper behavior is not confusing
- add/edit/remove actions remain clearly scoped to one instance
- deleting one instance does not look like deleting the whole machine
- shared machine state is not accidentally removed when one instance is edited or removed

### Scenario 4: Migration Planning

Goal:
- prove planning is accurate and non-mutating

Run:

1. create migration plan A -> B
2. inspect plan output carefully
3. verify remote state did not change

Check:

- source and target are obvious
- naming policy effects are understandable
- route through local temp is shown clearly
- warnings and errors read like operator guidance, not internal debug text

### Scenario 5: Successful Migration

Goal:
- prove the full happy path works on real hosts

Run:

1. execute a saved valid migration plan
2. observe progress carefully
3. inspect:
   - source service
   - local temp artifacts
   - target service
   - grouped UI
   - config state after completion

Check:

- source stops at the correct time
- target starts successfully
- assignment changes only after target verification
- post-success state is understandable to the user
- source cleanup is clearly deferred

### Scenario 6: Forced Failure + Rollback

Goal:
- prove failed migration is recoverable

Run:

1. create new migration plan
2. force failure on target
3. execute migration
4. confirm failure state
5. run rollback
6. inspect source/target/controller state

Check:

- rollback restores source service
- rollback removes partial target runtime
- rollback removes temporary archives
- UI explains what happened
- the user is not left guessing whether source or target is authoritative

### Scenario 7: Successful Finalization

Goal:
- prove post-success cleanup is explicit and safe

Run:

1. start from an executed migration
2. run finalization
3. test:
   - without source-volume deletion
   - with source-volume deletion on disposable data

Check:

- finalization language is explicit enough
- dangerous cleanup choices are not too easy to trigger by mistake
- target remains healthy after cleanup

### Scenario 8: Persistence Across Restart

Goal:
- prove state survives closing and reopening the CLI

Run:

1. exit `r1setup`
2. reopen it
3. reload the same config
4. inspect machine/instance view and migration state

Check:

- no stale or contradictory migration state
- no duplicate nodes
- no lost assignment or topology information

## What To Capture For Every Scenario

For each scenario, capture:

- scenario id and name
- machine set used
- config name used
- exact menu path
- action taken
- expected result
- actual result
- CLI output summary
- remote-state summary
- pass/fail

If failure occurs, also capture:

- exact error text
- whether issue is:
  - technical/backend
  - UX/UI
  - both
- whether there is data-risk or lockout-risk
- whether rollback was needed

## UX/UI Review Checklist

While executing the scenarios, actively look for:

- unclear menu wording
- misleading defaults
- too many steps for a common task
- missing context about current config/environment
- warnings that are too vague
- status labels that do not match actual machine state
- terminology mismatch:
  - machine
  - node
  - instance
  - service
  - deployment
  - migration
- unclear behavior when editing one node on a multi-node machine
- unclear behavior when removing one node from a multi-node machine
- places where the user could misunderstand:
  - whether an action is destructive
  - whether an action is planning-only
  - whether cleanup is explicit or automatic
  - whether standard vs expert mode is in effect
- flows that are technically correct but mentally hard to follow

## UX Issue Format

Record UX issues in this structure:

- `UX-<number>`
- area:
  - menu
  - status view
  - migration planning
  - migration execution
  - rollback
  - finalization
  - expert mode
- severity:
  - low
  - medium
  - high
- observed behavior
- why a real operator could misunderstand it
- recommended change

Example:

- `UX-01`
- area: migration execution
- severity: medium
- observed behavior: after success, the menu only says migration completed, but source cleanup remains deferred
- why confusing: user may assume source is already safe to delete or already removed
- recommended change: add explicit post-success banner saying `Target is live. Source cleanup has NOT happened. Use Finalize Migration when ready.`

## Technical Issue Format

Record technical issues in this structure:

- `BUG-<number>`
- scenario
- severity:
  - low
  - medium
  - high
  - critical
- exact action
- expected behavior
- actual behavior
- remote evidence
- config/state impact
- recovery action needed

## Output Deliverables After Live Test Run

After the live test session, produce:

1. scenario-by-scenario result table
2. list of technical bugs
3. list of UX/UI issues
4. release recommendation:
   - ready
   - ready with caveats
   - not ready
5. top fixes recommended before public rollout

## Release Decision Rule

Recommend **not ready** if any of these occur:

- assignment changes at the wrong moment
- rollback cannot restore source cleanly
- finalization removes too much shared state
- standard users are exposed to confusing expert behavior
- status UI materially misrepresents live machine state
- operator cannot reliably tell what is safe to do next

Recommend **ready with caveats** only if:

- core flows are correct
- remaining issues are mostly wording, visibility, or non-destructive confusion

## Execution Notes

This document is meant to be used together with:

- [20260319_230340_e2e_validation_checklist.md](/home/vi/work/ratio1/repos/multi_node_launcher/docs/20260319_230340_e2e_validation_checklist.md)

The checklist defines what must be validated.
This protocol defines how to execute and report it on real hosts.
