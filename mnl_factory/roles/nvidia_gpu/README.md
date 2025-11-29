# NVIDIA GPU Role

This role manages complete NVIDIA GPU setup including driver installation, container toolkit configuration, monitoring, and optimization.

## Requirements

- Ubuntu/Debian-based system
- NVIDIA GPU(s)
- Secure Boot disabled in BIOS
- Docker installed (for container toolkit configuration)
- Internet access for package downloads

## Role Variables

```yaml
# defaults/main.yml
nvidia_driver_version: "535"      # NVIDIA driver version to install
cuda_version: "12.2"              # CUDA version to install
enable_gpu_monitoring: true       # Enable GPU monitoring tools
enable_gpu_metrics: true         # Enable GPU metrics collection
gpu_power_limit: null            # GPU power limit in watts (null for default)
gpu_memory_limit: null           # GPU memory limit in MB (null for default)
```

## Dependencies

- docker (for container toolkit configuration)

## Example Playbook

```yaml
- hosts: gpu_nodes
  roles:
    - role: nvidia_gpu
      vars:
        cuda_version: "12.2"
        enable_gpu_monitoring: true
        gpu_power_limit: 250
```

## Role Tasks

The role performs the following tasks:

1. Pre-installation Checks
   - Detects NVIDIA GPUs
   - Checks current driver status
   - Validates Secure Boot is disabled

2. Driver Installation
   - Removes existing drivers (if necessary)
   - Installs specified driver version
   - Sets up DKMS modules

3. Container Toolkit Setup
   - Installs NVIDIA Container Toolkit
   - Configures Docker to use NVIDIA runtime
   - Restarts Docker service

4. Monitoring Setup
   - Installs nvtop for GPU monitoring
   - Validates driver installation with nvidia-smi

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian 