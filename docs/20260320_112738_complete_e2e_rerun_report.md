# Complete E2E Rerun Report

Timestamp: `2026-03-20T11:27:38+02:00`

## Scope

This report covers a fresh repo-local `r1setup` end-to-end rerun using:

- source repo CLI: `mnl_factory/scripts/r1setup`
- isolated dev home: `/tmp/r1setup-e2e-pass`
- remote machines:
  - `35.228.69.214` (`machineg1`)
  - `34.88.90.109` (`vitalii@34.88.90.109:22`)

The rerun exercised:

1. machine registration
2. post-registration discovery/import
3. grouped fleet/status views
4. migration planning
5. successful migration execution
6. migration finalization
7. expert-mode add/remove on one machine
8. interrupted reverse migration
9. rollback recovery

## Initial Remote State

- `35.228.69.214`
  - existing `edge_node.service` active
  - `edge_node` container running
- `34.88.90.109`
  - no active `edge_node` service
  - no `edge_node` container

## What Went Well

### 1. Registration and discovery handoff

- registering `35.228.69.214` as `machineg1` worked
- machine spec probe succeeded and displayed `4 CPU / 15.6 GiB RAM`
- after accepting the discovery prompt, the machine was passed directly into discovery
- redundant machine re-selection was no longer required

### 2. Discovery/import flow

- discovery found the existing runtime on `35.228.69.214`
- the candidate line was high-signal and operator-readable:
  - service state
  - inferred environment
  - container name
  - mount path
- selective import into the current config worked
- the imported node appeared correctly in grouped views

### 3. Migration planning

- migration plan review was clear and operationally useful
- route was explicit:
  - `source -> local temp -> target`
- preflight information was useful:
  - source volume size
  - controller free space
  - target free space
  - target preparation state

### 4. Successful migration execution

- target preparation succeeded
- source stop/archive/download/upload/extract/apply all completed
- target runtime verification passed
- application health was reported as verified
- assignment updated to the target machine

### 5. Successful finalization

- finalization completed successfully
- source cleanup remained deferred until explicit operator confirmation
- the core happy-path migration lifecycle worked end to end

### 6. Expert-mode add/remove on the same machine

- adding a second node on the same machine correctly triggered the expert-mode gate
- the user was warned that:
  - this is an expert-mode operation
  - recommended minimum is `4 CPU / 16 GiB RAM`
  - existing runtime names are preserved
  - new expert-mode instances get unique runtime names
- after add, grouped status showed:
  - running imported node
  - undeployed sibling
- undeployed sibling was correctly marked:
  - `NOT DEPLOYED`
  - `[N/A]` for service update actionability
- removing the undeployed sibling worked
- machine remained in expert mode explicitly after removal, with a clear explanation

### 7. Interrupted reverse migration and rollback

- reverse migration plan from `34.88.90.109` back to `machineg1` saved successfully
- interrupting execution left a recoverable saved plan in `executing` state
- rollback menu was available and completed successfully
- post-rollback remote state was correct:
  - source host `34.88.90.109`: `edge_node` active
  - target host `35.228.69.214`: no active `edge_node`

## Confirmed UX / State Issues

### 1. Deployment-record messaging remains misleading

This wording still appeared repeatedly:

- `Live runtimes were detected for this configuration, but there is no completed r1setup deployment record in the current config yet.`

It showed up even after:

- import
- successful migration execution
- successful finalization
- rollback back to a healthy running source

From an operator perspective this is confusing. The config clearly has launcher-tracked live state, but the message still implies deployment state is incomplete or unofficial.

### 2. Finalization and rollback review screens still reuse planning language

During finalize and rollback, the review screen still contained planning-time text such as:

- `Planning only: no source shutdown, assignment change, or data transfer has occurred.`

and old planning warnings such as target-preparation reminders.

That is functionally harmless but misleading during execution-oriented flows.

### 3. Long silent periods remain a UX issue during migration

Two phases were notably quiet:

- target preparation
- target apply/start

In both cases the underlying Ansible work was still running, but the CLI surface stayed silent for long enough to look stuck.

This is not a correctness failure, but it still degrades operator confidence.

### 4. Cancellation semantics are only partially clear

Interrupting reverse migration with `Ctrl+C` produced:

- `Operation cancelled by user.`

The source stayed healthy and the target remained clean, which is good.

However, the saved migration plan remained in `executing` state with `last_step=target_prepared`, and the operator has to know to use rollback afterward. That is workable, but the product could explain this recovery handoff more clearly at cancellation time.

### 5. Post-migration grouped view may be surprising

After finalized migration, the old source machine still appeared in grouped status as:

- `No Instances`
- plus `discovered on this machine but not imported into this config`

This is technically consistent with discovery state, but some operators may read it as stale clutter after a successful finalized move.

## Non-Issues / Things That Looked Good On Rerun

- the earlier false-running attribution for undeployed siblings did not reappear
- same-machine add did not create duplicate machine identities
- remove-node persisted correctly
- spec display stayed at `15.6 GiB`, which is operator-friendly on near-16-GB hosts
- rollback restored clean source ownership of the logical instance

## Input / Runner Artifacts Not Counted As Product Bugs

One attempted add-node path earlier in the rerun became prompt-desynchronized because input was buffered too aggressively across redraws. That attempt was discarded as a PTY/test-runner artifact, not recorded as a product defect.

Only the later careful same-machine add/remove pass is treated as authoritative product feedback.

## Final Remote State

At the end of this rerun:

- `34.88.90.109`
  - `edge_node.service` active
  - `edge_node` container running
- `35.228.69.214`
  - no active `edge_node` runtime

Config state:

- one tracked live node remains
- saved migration plan is in `rolled_back` state after the reverse-migration rollback

## Overall Assessment

This rerun materially confirms that the current implementation is functionally strong across the main lifecycle:

- discovery/import
- successful migration
- finalization
- expert-mode same-machine add/remove
- interrupted migration with rollback

The remaining problems are now mostly UX/state-model presentation issues rather than core workflow breakage.

## Recommended Follow-Up Order

1. fix the misleading `no completed deployment record` messaging
2. specialize finalize/rollback review text so it no longer says `Planning only`
3. improve migration progress visibility during long Ansible phases
4. clarify cancellation recovery messaging when a saved plan remains recoverable but not finalized
5. decide whether post-finalization discovery-only machine rows should be collapsed, filtered, or left as-is
