# Docker Role

This role installs and configures Docker with NVIDIA Container Toolkit support for GPU-enabled containers. It sets up Docker daemon with proper GPU access and configuration.

## Requirements

- Ubuntu-based system
- NVIDIA drivers installed (handled by nvidia_drivers role)
- Internet access for package downloads

## Role Variables

```yaml
# defaults/main.yml
docker_version: "latest"           # Docker version to install
docker_compose_version: "2.21.0"   # Docker Compose version
enable_nvidia_runtime: true        # Enable NVIDIA Container Runtime
docker_users: []                   # List of users to add to docker group
```

## Dependencies

- nvidia_drivers (when enable_nvidia_runtime is true)

## Example Playbook

```yaml
- hosts: gpu_nodes
  roles:
    - role: docker
      vars:
        docker_version: "latest"
        enable_nvidia_runtime: true
        docker_users:
          - ubuntu
          - admin
```

## Role Tasks

The role performs the following tasks:

1. Docker Installation
   - Adds Docker repository
   - Installs Docker Engine
   - Installs Docker Compose

2. NVIDIA Container Runtime Setup
   - Installs NVIDIA Container Toolkit
   - Configures Docker daemon for GPU support
   - Sets up NVIDIA runtime as default (optional)

3. Configuration
   - Sets up Docker daemon options
   - Configures user permissions
   - Enables and starts Docker service

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian 