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
- Set `R1SETUP_NO_CLEAR=0` if you want the old clear-screen behavior during a dev run.
- `--use-real-configs` means changes to active config selection and saved configs will affect your real `~/.ratio1/r1_setup`.
- Run `bash /home/vi/work/ratio1/repos/multi_node_launcher/scripts/run_r1setup_repo_local.sh --help` for all options.

## Features
### Node Management
- Configure GPU nodes (IP, SSH, authentication)
- View current configuration
- Test node connectivity

### Deployment  
- Full deployment (Docker + NVIDIA + GPU)
- Docker-only deployment

### Operations
- Start, stop, and restart deployed services
- Re-apply the current versioned service file from `Operations -> Update Service File`
- On startup, `r1setup` may offer a direct service-file update prompt when deployed nodes are behind the current target version
- Applied service definitions also render launcher metadata inside the shared persistent volume at `/var/cache/edge_node/_local_cache/_data/r1setup/metadata.json`, exposed in-container via `R1SETUP_METADATA_PATH`

### Information
- Get node information
- Display/export node addresses

### Settings
- Change network environment (mainnet/testnet/devnet)

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
Old script functionality is preserved:
- 3_configure.py → "Configure nodes" menu
- 4_run_setup.sh → "Deploy" options

All existing configurations remain compatible. 
