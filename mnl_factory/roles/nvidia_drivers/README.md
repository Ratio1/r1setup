# NVIDIA Drivers Role

This role handles the installation and configuration of NVIDIA GPU drivers. It includes automatic GPU detection, driver installation, and validation of the installation.

## Requirements

- Ubuntu-based system
- NVIDIA GPU(s)
- Secure Boot disabled in BIOS
- Internet access for package downloads

## Role Variables

```yaml
# defaults/main.yml
nvidia_driver_version: "535"       # NVIDIA driver version to install
nvidia_driver_branch: "production" # Driver branch (production/beta)
force_driver_install: false       # Force reinstall even if drivers exist
enable_persistence_mode: true     # Enable NVIDIA persistence daemon
```

## Dependencies

- prerequisites

## Example Playbook

```yaml
- hosts: gpu_nodes
  roles:
    - role: nvidia_drivers
      vars:
        nvidia_driver_version: "535"
        force_driver_install: false
```

## Role Tasks

The role performs the following tasks:

1. Pre-installation Checks
   - Detects NVIDIA GPUs
   - Checks current driver status
   - Validates system requirements

2. Driver Installation
   - Removes existing drivers (if necessary)
   - Adds NVIDIA package repository
   - Installs specified driver version
   - Sets up DKMS modules

3. Post-installation Setup
   - Configures driver parameters
   - Sets up persistence mode
   - Validates driver installation
   - Configures GPU settings

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian 