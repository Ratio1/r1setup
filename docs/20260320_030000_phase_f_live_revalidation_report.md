## Phase F Live Revalidation Report

Timestamp: `2026-03-20T03:00:00+02:00`

Environment:
- repo-local `r1setup` via `scripts/run_r1setup_repo_local.sh`
- dev home: `/tmp/r1setup-dev`
- active config: `reval-devnet_20260320_0147_1n`
- test machines:
  - `35.228.69.214` (`machineb`, `r1-vi-g1`)
  - `34.88.90.109` (`vitalii@34.88.90.109:22`, `r1-vi-g2`)

Goal:
- rerun the remaining live scenarios after Phases A-E
- verify the timeout, rollback, shared-machine, and expert-mode fixes on real hosts

## Executed Scenarios

1. Prepare registered machine
- target machine: `machineb` on `35.228.69.214`
- result: success
- observed UX:
  - completion recap now ends with:
    - `Preparation finished at machine scope only. No Edge Node instances were deployed or started.`
  - this resolved the earlier ambiguity around what machine prep actually changed

2. Forward migration plan
- source: `nodea` on `34.88.90.109`
- target: `machineb` on `35.228.69.214`
- naming policy: `preserve`
- result: success
- observed:
  - plan review showed the expected route:
    - `vitalii@34.88.90.109:22 -> local temp -> machineb`
  - preflight values looked coherent

3. Forward migration execution
- source: `34.88.90.109`
- target: `35.228.69.214`
- result: success
- observed:
  - step banners advanced through all `9/9` stages
  - no false `30s` lifecycle timeout occurred
  - completion summary reported:
    - source service stopped: yes
    - archive verified: yes
    - target runtime verified running: yes
    - application health: verified
    - assignment updated: yes

4. Same-machine second-instance add
- added `nodeb` on the same machine as `nodea` (`35.228.69.214`)
- result: success
- observed:
  - explicit expert-mode gate triggered
  - machine/resource warning was shown before confirmation
  - existing runtime preservation and unique new runtime naming were explained clearly
  - post-add node list showed:
    - `nodea` running
    - `nodeb` never deployed

5. Shared-machine status refresh
- topology: one deployed instance (`nodea`) and one undeployed sibling (`nodeb`) on `35.228.69.214`
- result: core correctness fixed
- observed:
  - `nodeb` stayed `NOT DEPLOYED`
  - `nodeb` no longer inherited `nodea`'s running status
  - grouped machine view correctly showed mixed states on one machine

6. Remove extra sibling
- removed `nodeb`
- result: success
- observed:
  - config returned to one node
  - CLI explicitly stated that the machine remains in `expert` mode
  - runtime-stability explanation was shown

7. Interrupted reverse migration plus rollback
- planned reverse migration:
  - source: `machineb` / `35.228.69.214`
  - target: `34.88.90.109`
- intentionally interrupted execution during early runtime steps
- actual interrupted state:
  - saved plan: `status=executing`, `last_step=target_prepared`
  - `edge_node` inactive on both machines immediately after interruption
- rollback result: success
- post-rollback state:
  - saved plan: `status=rolled_back`, `last_step=rollback_completed`, `last_error=null`
  - source machine `35.228.69.214` restored to:
    - `edge_node` active
    - `edge_node` container running
  - target machine `34.88.90.109` remained inactive

## What Went Well

- migration no longer fails just because service lifecycle work exceeds `30s`
- rollback successfully restored service on the real interrupted migration path
- shared-machine status attribution is now instance-correct
- expert-mode gating for same-machine add is now explicit and understandable
- remove-node persistence/topology messaging behaved as designed
- machine-prep recap is clearer and more trustworthy

## Remaining Issues

1. Main-menu compact deployment label can still be stale on first render.
- On fresh startup, the compact line still showed:
  - `✗ not deployed`
- at the same time, the suggestion line already said:
  - `Suggested: Review tracked live nodes before deploying changes`
- after returning from a refreshed status screen, the compact line corrected itself to:
  - `📡 tracking 1 live node(s)`
- likely cause:
  - the compact main-menu header is evaluated before current inventory state is loaded/refreshed for that screen

2. `Node Status & Info` still recommends service-file update for an undeployed sibling.
- with:
  - `nodea` running
  - `nodeb` not deployed
- the screen correctly showed `nodeb` as `NOT DEPLOYED`, but the recommendation block still said:
  - `Update service for: nodeb`
- this is misleading because there is no deployed service/runtime to update yet
- recommendation logic should skip:
  - `not_deployed`
  - `never_deployed`
  - `NOT FOUND` service/runtime states

3. Old pre-fix `rollback_failed` saved plans are not auto-repaired.
- the stale historic plan from the earlier broken run stayed non-rollback-eligible
- a newly interrupted migration under the fixed code did roll back correctly
- this is lower priority than the live-path fixes, but still worth documenting

## Final State After Revalidation

Config/runtime:
- active instance: `nodea`
- assigned machine in saved config: `machineb`
- saved migration plan: `rolled_back`

Remote hosts:
- `35.228.69.214`
  - `edge_node.service`: active
  - `edge_node` container: running
- `34.88.90.109`
  - `edge_node.service`: inactive
  - no running `edge_node` container

## Conclusion

The core remediation goals are materially met on real hosts:
- long-running migration paths work
- rollback recovery works on a real interrupted execution
- shared-machine status is no longer falsely optimistic
- expert-mode same-machine add/remove is now much safer

The remaining work is mostly follow-up UX polish:
- fix stale compact deployment text on first render
- suppress update recommendations for undeployed siblings
- optionally add repair behavior for legacy stuck migration plans
