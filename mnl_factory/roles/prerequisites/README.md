# Prerequisites Role

This role sets up the basic system requirements needed for GPU node deployment. It handles system package updates, installation of essential tools, and configuration of system settings.

## Requirements

- Ubuntu-based system
- Sudo privileges
- Internet access for package downloads

## Role Variables

```yaml
# defaults/main.yml
update_system: true              # Whether to run system updates
install_essential_packages: true # Whether to install essential packages
```

## Dependencies

None.

## Example Playbook

```yaml
- hosts: gpu_nodes
  roles:
    - role: prerequisites
      vars:
        update_system: true
        install_essential_packages: true
```

## Role Tasks

The role performs the following tasks:

1. System Updates
   - Updates package cache
   - Upgrades system packages (if enabled)
   - Installs essential build tools and dependencies

2. System Configuration
   - Sets up required system parameters
   - Configures system limits and settings
   - Prepares system for GPU driver installation

3. Package Installation
   - Installs required packages for GPU support
   - Sets up development tools
   - Configures package repositories

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian 