# r1setup - Unified Multi-Node Launcher Setup

## Overview
`r1setup` replaces the old individual scripts (3_configure.py, 4_run_setup.sh) with a unified, user-friendly interface.

## Installation
```bash
curl -sSL https://raw.githubusercontent.com/Ratio1/r1setup/refs/heads/main/install.sh | bash
```

## Usage
After installation, run from anywhere:
```bash
r1setup
```

## Repo Dev Workflow
To test the repo version of `r1setup` and the repo collection locally before publishing changes, use:

```bash
bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh
```

Use your real saved `r1setup` configs:

```bash
bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh --use-real-configs
```

Use a custom config store:

```bash
bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh --config-source /path/to/r1_setup
```

Notes:
- By default, the helper keeps terminal output visible and does not clear the screen between menus.
- By default, the helper also skips startup auto-update checks so local repo testing does not wipe the synced dev collection when offline.
- Set `R1SETUP_NO_CLEAR=0` if you want the old clear-screen behavior during a dev run.
- Set `R1SETUP_SKIP_AUTO_UPDATE=0` if you explicitly want startup auto-update behavior during a dev run.
- `--use-real-configs` means changes to active config selection and saved configs will affect your real `~/.ratio1/r1_setup`.
- Run `bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh --help` for all options.

## Features
### Machine-First Onboarding
- First-run configuration starts from machines, not nodes
- Register machines with SSH details and optional hardware spec probes
- Batch discovery scans all registered machines for existing `edge_node` services
- Discovered running services are imported (not redeployed) with preserved runtime names
- Fresh instances are only created on machines confirmed clean by the scan
- Simple mode (default): one instance per machine, no topology prompts
- Advanced mode (opt-in): multiple instances per machine with capacity guidance
- Deploy prompt defaults to `n` and only appears when fresh instances were created

### Instance Management
- Add, edit, and remove individual instances
- View current configuration
- Test node connectivity

### Deployment
- Full deployment (Docker + NVIDIA + GPU)
- Docker-only deployment
- Prepare registered machines without deploying an Edge Node yet
- Plan an Edge Node migration before any data transfer or source shutdown happens
- Default machine topology remains `standard`: one machine, one Edge Node
- Multi-node-per-machine workflows stay explicit under `expert` mode

### Operations
- Start, stop, and restart deployed services
- Re-apply the current versioned service file from `Operations -> Update Service File`
- On startup, `r1setup` may offer a direct service-file update prompt when deployed nodes are behind the current target version
- Applied service definitions also render launcher metadata inside the shared persistent volume at `/var/cache/edge_node/_local_cache/_data/r1setup/metadata.json`, exposed in-container via `R1SETUP_METADATA_PATH`

### Information
- Get node information
- `Fleet Summary` and `Node Status & Info` now group instances by physical machine, so expert-mode multi-instance hosts and empty registered machines are shown explicitly while standard one-machine-one-node setups remain concise
- Discovery scans can now keep showing services found on a machine even when you choose not to import them into the current config
- Display/export node addresses
- Remote host data collection guidance lives in [`../../docs/20260609_141041_remote_host_data_collection.md`](../../docs/20260609_141041_remote_host_data_collection.md)

### Settings
- Change network environment (mainnet/testnet/devnet)

## Help & FAQ
Open `Main Menu -> Help & FAQ` for read-only operator guidance inside the CLI. The menu is also
available from the first-run configuration-required prompts, so users can read the concepts before
creating or importing a config.

Current topics:

- Core concepts
- First-time setup
- Register Machine vs Add Node
- Discovery and import
- Deployment and Prepare Machines
- Migration workflow
- Rollback vs Finalize Migration
- Service file updates
- SSH/auth troubleshooting
- Common mistakes

The migration help explicitly covers the standard target rule: register the destination machine,
do not add it as a node first, then use `Deployment Menu -> 4) Migration` to move the existing node
assignment in the same config.

## Discovery And Import
Discovery and import are integrated into the first-run onboarding flow. They are also available standalone under `Configuration Menu`:

- `Register Machine`: add a fleet machine without deploying a node (delegates to the same shared registration helper used by onboarding)
- `Discover Services`: scan a registered machine for existing remote `edge_node` services and import only the ones you choose

If `Register Machine` is not visible in an existing config, switch the config to Advanced Mode first.
That switch is one-way because advanced configs can represent machine-level state that simple mode
does not expose.

Discovery/import rules:

- discovery is read-only on the remote host
- import is selective; unselected services stay untouched
- discovered runtime names are preserved by default on import
- names like `edge_node2` or `edge_node3` do not by themselves imply expert mode
- if importing selected services would make one machine track multiple instances in the current config, `r1setup` requires explicit expert-mode confirmation
- discovery can warn when another saved config already tracks the same remote `(machine endpoint + service name)`

### SSH Key Management
- Install an SSH public key on selected password-auth hosts
- Verify controller-side SSH key login before switching inventory auth
- Add extra public keys without changing the primary host auth
- Validate legacy or migrated key-auth hosts before hardening
- Disable SSH password authentication only after successful key verification

## SSH Key Management
Open `Advanced Menu -> SSH Key Management`.

Available actions:
- `Install Key / Migrate Password Hosts`
- `Add Extra Public Key`
- `Validate Key Authentication`
- `Disable Password Authentication`
- `Show SSH Auth Status`

### Recommended Order
1. Install a key on password-auth hosts.
2. Verify key-based login succeeds.
3. Check `Show SSH Auth Status` and confirm the host is `key_verified`.
4. Disable password authentication only after validation succeeds.

### Important Warnings
- Disabling password authentication changes the machine's SSH daemon policy, not only `r1setup`.
- Some cloud providers also require the public key in the provider dashboard or instance metadata.
- Always keep the private key secure and store at least one recovery key outside the target machine.
- A failed hardening verification triggers rollback logic, but you should still test this on disposable hosts first.

### SSH States
- `password_only`: Host still uses password authentication in inventory.
- `key_configured_legacy`: Host already had key auth before SSH metadata existed; validate it before hardening.
- `key_installed_unverified`: Key was installed, but login has not been confirmed yet.
- `key_verified`: Key login succeeded and the host is eligible for hardening.
- `verification_failed`: Key login failed; fix access and revalidate.
- `password_disabled`: Password authentication was disabled successfully.

## File Structure
```
~/.ratio1/r1_setup/r1setup    # Main script
/usr/local/bin/r1setup                # System-wide command
```

## Migration
Migration lives under `Deployment Menu -> 4) Migration`. The menu shows the saved plan (status,
last step, last error) and offers only the actions that are valid for it:

| Plan status | Actions offered |
|---|---|
| no plan, `finalized`, `rolled_back`, `abandoned` | Plan a new migration |
| `rolled_back` with a target copy that may still run (typed override) | Remove the node copy left on the target, Plan a new migration |
| `planned`, `blocked` | Execute, replace the plan, Abandon |
| `executing`, `failed`, `rolling_back`, `rollback_failed` | Roll back (retry), Abandon |
| `executed`, `finalizing`, `finalization_failed` | Finalize (retry), Finalize without source cleanup, Abandon |

Every status has a forward action, so an error, a dead host or Ctrl-C never leaves a plan stuck.
Ctrl-C during a migration action returns to the menu with the next step instead of exiting.
The main menu and the Deployment Menu show a banner while a migration is open.

Target machine rule:

- Register the destination machine; do not `Add Node` on it first. In standard mode an added node
  creates an assigned instance placeholder and the target is no longer empty.
- If no destination is registered, `Plan a new migration` offers to register one inline. This works
  in simple mode; no switch to Advanced Mode is needed.
- Execute moves the selected existing node onto the registered target machine and updates its
  assignment in the same config; do not add that node to the config again afterward.
- For the in-app explanation, open `Main Menu -> Help & FAQ -> Migration workflow`.

Planning (non-mutating) checks:

- reachability of both hosts, source volume size, controller temp space, target volume free space
- free space in `/tmp` on the source (the archive is written there after the node stops) and on
  the target (archive, plus the extracted volume when `/tmp` shares its filesystem)
- an existing service unit or volume on the target with the same runtime names (a leftover copy);
  the plan is blocked with a cleanup hint
- a rough downtime estimate from the volume size

Execution follows:

- source machine -> local controller temp folder -> target machine
- target preparation before transfer when needed
- source stop **and disable** before archive creation, so a source reboot cannot start a second copy
  with the same `e2.pem`
- assignment finalization only after target verification succeeds
- application health is reported `verified` only when the target node rewrites
  `_data/local_info.json` after it started (up to 2 min); otherwise `unverified`
- a failed step prints one block: step, host, short cause, source/target state, next action, and the
  path of the full output log (next to the operation log)

Rollback / finalize / abandon:

- Rollback restores the source first (re-enable + start) and then removes target files and transfer
  archives where reachable; anything it cannot remove is listed as a leftover. If the target may
  already run the node, it is stopped first; if it cannot be reached, restarting the source requires
  typing the node name (duplicate-identity risk).
- Finalize removes the stopped copy from the source (unit, container, metadata, and the global helper
  scripts when no other instance is left there). Deleting the source volume is optional; the prompt
  says it holds the node key (`e2.pem`). A receipt lists what was removed and kept.
- Finalize without source cleanup closes a migration whose source host is gone (typed confirmation);
  the old disk still holds `e2.pem`.
- Abandon closes the plan without contacting any host, after showing what is on each host.
- Rollback cleans the target first whenever the last completed step is not known to be before the target could run the node (this includes plans saved by older r1setup versions).
- Register Machine refuses a `user@host:port` that is already registered (it would otherwise be merged into, and rename, the existing machine).
- Review screens for these actions probe both hosts live (service, container, volume, archive,
  node-key fingerprint) instead of reprinting the planning-time preflight.
- Closed plans are kept in a short history (last 10) shown in the Migration menu.

Security:

- sudo passwords for migration commands are sent to `sudo -S` on stdin, and SSH passwords reach
  `sshpass -e` through the environment; neither appears in the process list.
- migration `ssh`/`scp` use `ServerAliveInterval` and honour the host's `ansible_ssh_common_args`
  (for example `ProxyJump`).

Existing configurations remain compatible.

Legacy note:

- older saved migration plans that were left in a stale `rollback_failed` state can now be normalized automatically when `r1setup` can prove the source assignment is still authoritative and the saved source node status is already `running`
