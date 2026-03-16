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
