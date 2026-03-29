# E2E Migration Dry Test Report

Timestamp: `2026-03-28T18:45:00+03:00`

## Purpose

Validate the full migration lifecycle on real remote machines using the `r1setup` CLI driven via `pexpect` automation through the repo-local dev runner.

This is a **dry test**: the migration is executed for real, verified on the target, then cleaned up manually. The goal is to confirm the flow is coherent and every step works as expected end-to-end.

## Test Environment

- CLI source: `mnl_factory/scripts/r1setup` on branch `nodes-migration`
- Runner: `scripts/run_r1setup_repo_local.sh --reset` (isolated dev HOME)
- Automation: Python `pexpect` driver at `temp/e2e_migration_test.py`
- Source machine: `ubuntu@51.83.248.38` (hostname `dr1-v100s-1`, existing `edge_node` service running, devnet)
- Target machine: `vitalii@35.228.69.214` (hostname `r1-vi-g1`, empty, 4 CPU / 15.6 GiB RAM)
- Controller: local workstation (`/home/vi`)

## How The Automated Driver Works

The `pexpect`-based driver (`temp/e2e_migration_test.py`) launches the repo-local `r1setup` with `R1SETUP_NO_CLEAR=1` and `R1SETUP_SKIP_AUTO_UPDATE=1`, then drives it through the full interactive CLI by pattern-matching prompts and sending responses.

Key patterns used:

- Menu prompts: `Select option`, `Select instance`, `Select machine`, `Select target machine`
- Input prompts: `Enter host`, `Enter SSH username`, `Enter machine label`, etc.
- Confirmation prompts: `(y/n)`, `(Y/n)`, `(y/N)` - all matched via `\([yY]/[nN]\)`
- Continuation prompts: `Press Enter`
- Password prompts: `sudo password` (handled via pexpect pseudo-TTY, no real password needed)

The driver runs phases sequentially: config creation, machine registration, migration planning, execution, status check, rollback attempt, and exit.

## Phases Executed

### Phase 1: Config Creation

Created `e2e-migration-test` config with:
- Environment: mainnet
- 1 node: `source-node` at `ubuntu@51.83.248.38` with SSH key auth

Result: Config created and activated. Deploy offer declined.

### Phase 2: Target Machine Registration

Registered `target-g1` at `vitalii@35.228.69.214`:
- Topology: standard
- SSH key auth
- Spec probe: 4 CPU / 15.6 GiB RAM detected
- Discovery offer: declined (target is empty)

Result: Machine registered successfully.

### Phase 3: Fleet Summary

Fleet summary showed 2 machines:
- `target-g1`: standard, empty, no instances
- `ubuntu@51.83.248.38`: standard, source-node assigned (never deployed status)

### Phase 4: Migration Planning

Planned migration of `source-node` from `ubuntu@51.83.248.38` to `target-g1`:

- Naming policy: preserve
- Transfer route: `ubuntu@51.83.248.38:22 -> local temp -> target-g1`
- Source archive path: `/tmp/r1setup_migration_source_node.tar.gz`
- Local archive path: `~/.ratio1/dev_local_r1setup_home/.ratio1/migration_tmp/source_node.tar.gz`
- Target archive path: `/tmp/r1setup_migration_source_node.tar.gz`
- Preflight: source volume 1.75 GB, controller 37 GB free, target 74.8 GB free
- Warning: target not yet prepared (will be prepared during execution)

Plan saved as `migration-source_node-20260328181225`.

### Phase 5: Migration Execution

Execution steps observed in order:

1. **Target machine preparation** via `prepare_machine.yml`
   - Ansible result: `ok=49 changed=6 unreachable=0 failed=0 skipped=64 rescued=0 ignored=1`
   - Docker verified running on target
   - No NVIDIA GPU detected on target (expected, CPU-only host)

2. **Source service stopped** before archiving

3. **Archive created** on source and checksum computed

4. **Archive downloaded** to controller temp folder with integrity validation

5. **Archive uploaded** to target with checksum verification

6. **Target volume created** with source ownership and permissions

7. **Archive extracted** into target volume path

8. **Service definition rendered** on target via `apply_instance.yml`
   - Ansible result: `ok=31 changed=10 unreachable=0 failed=0 skipped=3 rescued=0 ignored=0`

9. **Service started** on target via `service_start.yml`
   - Ansible result: `ok=11 changed=2 unreachable=0 failed=0 skipped=3 rescued=0 ignored=0`
   - Message: `SUCCESS: Edge Node service started on source-node, Service: edge_node, Status: active, Container: Running`

10. **Target health verified**

Final execution summary:
- Source service stopped: yes
- Archive verified across source, controller, and target: yes
- Target runtime verified running: yes
- Application health: verified
- Assignment updated to target machine: yes

Plan status moved to `executed`.

### Phase 6: Post-Migration Status

Deployment status showed:
- `target-g1`: `vitalii@35.228.69.214 | mode=standard | state=active | Running`
  - `source-node [RUNNING] service=edge_node container=edge_node`
- `ubuntu@51.83.248.38`: `mode=standard | state=prepared | No Instances`
- Saved Migration Plan: `source-node -> target-g1 [executed]`

Main menu showed: `tracking 1 live node(s)`, `Nodes (1): 1 running`.

### Phase 7: Rollback Attempt

Rollback correctly refused:
- `Saved migration plan is not rollback-eligible in status 'executed'.`
- This is correct behavior - rollback is only for failed/interrupted migrations, not successful ones.

### Phase 8: Manual Cleanup

After the automated test completed, the target was cleaned up manually:
- Stopped and disabled `edge_node.service` on target
- Removed Docker container and volume
- Removed temp archives on source, target, and controller
- Verified source machine returned to original state: `edge_node active, Up`
- Verified target machine clean: no edge_node service or containers

## Issues Found

### Issue 1: Source Service Auto-Restarts After Migration Stops It

After migration execution stopped the source service for archiving, the source `edge_node` came back up autonomously (`Up 10 seconds` when checked post-migration). This means both source and target were running simultaneously between execution completion and manual cleanup.

The migration correctly stops the source via `systemctl stop`, but the Docker container restart policy or systemd `Restart=` directive brings it back. This could cause duplicate instances running the same logical node data on two machines during the window between execution and finalization.

Severity: medium. The design defers source cleanup to explicit finalization, but the auto-restart creates an unintended dual-running window.

### Issue 2: Discovery Import Collision Message Was Unclear (Fixed)

When attempting to discovery-import `edge_node` on a machine where it was already tracked as `source-node`, the error was:

> `Discovered service 'edge_node' collides with existing runtime fields on machine 'ubuntu@51.83.248.38:22'.`

This did not explain which fields collided or what to do about it.

Fixed in commit `55a503f`: the message now shows the colliding fields and suggests skipping import for already-managed services.

### Issue 3: Cached Discovery Results Displayed Twice (Fixed)

In fleet summary, the `cached discovery results not imported into this config` section appeared twice for machines that had both tracked instances and untracked discovered candidates. The discovered candidates block was rendered once before instances and once after.

Fixed in commit `55a503f`: the pre-instance block now only renders for empty machines (inside the `if not instances` guard), and the post-instance block handles machines with instances.

### Issue 4: Discovery Correctly Detects Environment Mismatch

When the source machine runs `devnet` services but the config is set to `mainnet`, discovery correctly warns:

> `Selected services (edge_node) do not match the current config environment 'mainnet'. Continue importing them? (y/n) [n]:`

Default is `n` (safe). This is correct behavior.

### Issue 5: Expert Mode Gate on Multi-Instance Import

When trying to import a discovered service onto a machine that already tracks one instance, the CLI correctly warns:

> `Importing 1 service(s) onto machine will require expert mode because the machine would track 2 instances.`

And asks for explicit confirmation before promoting to expert mode. This is correct behavior.

## Verification Commands Used

```bash
# Run the automated driver
python3 temp/e2e_migration_test.py

# Post-test machine state verification
ssh ubuntu@51.83.248.38 "systemctl is-active edge_node.service; docker ps --format '{{.Names}} {{.Status}}' | grep edge"
ssh vitalii@35.228.69.214 "systemctl is-active edge_node.service; docker ps --format '{{.Names}} {{.Status}}' | grep edge"

# Target cleanup
ssh vitalii@35.228.69.214 "sudo systemctl stop edge_node.service; sudo systemctl disable edge_node.service; sudo docker rm -f edge_node; sudo rm -f /etc/systemd/system/edge_node.service; sudo systemctl daemon-reload; sudo rm -rf /var/cache/edge_node; sudo rm -f /tmp/r1setup_migration_source_node.tar.gz"
ssh ubuntu@51.83.248.38 "sudo rm -f /tmp/r1setup_migration_source_node.tar.gz"
rm -rf ~/.ratio1/dev_local_r1setup_home/.ratio1/migration_tmp/
```

## Overall Assessment

The migration lifecycle works end-to-end on real hosts:
- Config creation, machine registration, spec probing, and fleet visualization all work correctly
- Migration planning accurately shows route, preflight, and warnings
- Migration execution correctly prepares target, stops source, archives, transfers, extracts, renders, starts, and verifies
- Assignment update happens only after target verification succeeds
- Rollback correctly refuses for successfully executed plans
- Post-migration status accurately reflects the new machine assignment

The one notable concern is the source auto-restart creating a dual-running window (Issue 1). The remaining issues (2, 3) were fixed in commit `55a503f`.
