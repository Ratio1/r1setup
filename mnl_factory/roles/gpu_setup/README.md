# GPU Setup Role

This role automates the setup of GPU nodes with NVIDIA drivers and required dependencies. It handles the detection of NVIDIA GPUs, driver installation, and configuration of monitoring tools.

## Requirements

- Ubuntu-based system
- NVIDIA GPU(s) (the role will automatically skip GPU setup if no GPU is detected)
- Internet access for package downloads
- Secure Boot disabled in BIOS (required for NVIDIA driver installation)

## Role Variables

```yaml
# defaults/main.yml
nvidia_driver_version: "535"  # NVIDIA driver version to install
cuda_version: "12.2"         # CUDA version to install
```

## Dependencies

None.

## Example Playbook

```yaml
- hosts: gpu_nodes
  roles:
    - role: gpu_setup
      vars:
        nvidia_driver_version: "535"
        cuda_version: "12.2"
```

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian

## Role Tasks

The role performs the following tasks:

1. GPU Detection
   - Checks for NVIDIA GPU presence
   - Skips GPU-related tasks if no GPU is found

2. Driver Installation
   - Removes existing NVIDIA drivers
   - Installs specified NVIDIA driver version
   - Configures driver settings

3. Verification
   - Verifies driver installation
   - Checks GPU information
   - Sets up monitoring tools
