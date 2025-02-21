# Setup Role

This role orchestrates the complete setup of GPU nodes by coordinating the execution of other roles and performing final configuration tasks.

## Requirements

- Ubuntu-based system
- All requirements from dependent roles (prerequisites, nvidia_drivers, docker)

## Role Variables

```yaml
# defaults/main.yml
setup_monitoring: true           # Enable monitoring tools
setup_docker: true              # Enable Docker setup
setup_nvidia_drivers: true      # Enable NVIDIA driver setup
enable_automatic_updates: false # Enable automatic system updates
```

## Dependencies

- prerequisites
- nvidia_drivers
- docker

## Example Playbook

```yaml
- hosts: gpu_nodes
  roles:
    - role: setup
      vars:
        setup_monitoring: true
        setup_docker: true
        setup_nvidia_drivers: true
```

## Role Tasks

The role performs the following tasks:

1. Initial Setup
   - Validates system requirements
   - Configures basic system settings
   - Sets up monitoring tools (if enabled)

2. Role Coordination
   - Manages role execution order
   - Handles role dependencies
   - Ensures proper configuration across roles

3. Final Configuration
   - Validates complete setup
   - Configures automatic updates (if enabled)
   - Performs final system checks

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian 