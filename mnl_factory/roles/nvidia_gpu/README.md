# NVIDIA GPU Role

This role manages NVIDIA GPU configuration, monitoring, and optimization. It handles GPU-specific settings, CUDA installation, and performance tuning.

## Requirements

- Ubuntu-based system
- NVIDIA GPU(s)
- NVIDIA drivers installed (handled by nvidia_drivers role)
- Internet access for package downloads

## Role Variables

```yaml
# defaults/main.yml
cuda_version: "12.2"              # CUDA version to install
enable_gpu_monitoring: true       # Enable GPU monitoring tools
enable_gpu_metrics: true         # Enable GPU metrics collection
gpu_power_limit: null            # GPU power limit in watts (null for default)
gpu_memory_limit: null           # GPU memory limit in MB (null for default)
```

## Dependencies

- nvidia_drivers

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

1. CUDA Setup
   - Installs CUDA Toolkit
   - Configures CUDA environment
   - Sets up development tools

2. GPU Configuration
   - Configures GPU power management
   - Sets up GPU monitoring
   - Optimizes GPU performance

3. Monitoring Setup
   - Installs monitoring tools (nvtop, dcgm)
   - Configures metrics collection
   - Sets up GPU health checks

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian 