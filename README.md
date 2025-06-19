# Multi Node Launcher

**Quick Setup**: For an easy setup script and quick start instructions, please refer to the [README in mnl_factory](mnl_factory/README.md).

A comprehensive solution for setting up and managing GPU nodes with automated deployment using Ansible.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Directory Structure](#directory-structure)
- [Configuration](#configuration)
- [GPU Setup Process](#gpu-setup-process)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Post-Installation](#post-installation)
- [Notes](#notes)
- [Deployment Instructions](#deployment-instructions)

## Prerequisites

1. Ansible installed on your control node
2. SSH access to target nodes
3. Sudo privileges on target nodes
4. NVIDIA GPU(s) on target nodes (the playbook will automatically skip GPU setup if no GPU is detected)
5. Internet access for package downloads
6. Secure Boot disabled in BIOS (required for NVIDIA driver installation)

## Initial Setup

1. Install required Ansible collections:
```bash
ansible-galaxy collection install -r requirements.yml
```

2. Set up secrets:
   - Copy `group_vars/vault.yml.example` to `group_vars/vault.yml`
   - Edit `vault.yml` with your actual credentials
   - (Optional) Encrypt the vault file:
     ```bash
     ansible-vault encrypt group_vars/vault.yml
     ```

## Directory Structure

```
mnl_factory/
├── group_vars/
│   ├── all.yml         # Common variables
│   ├── vault.yml       # Encrypted secrets
│   └── vault.yml.example # Example secrets template
├── inventory/
│   └── hosts.yml       # Inventory file
├── playbooks/
│   └── site.yml        # Main playbook
├── roles/
│   ├── prerequisites/  # System prerequisites
│   ├── nvidia_gpu/    # NVIDIA GPU setup and driver installation
│   ├── docker/        # Docker installation
│   └── setup/         # Final configuration
├── requirements.yml    # Ansible Galaxy requirements
└── .gitignore         # Git ignore patterns
```

## Configuration

1. Edit `inventory/hosts.yml` to add your target nodes:
```yaml
all:
  children:
    gpu_nodes:
      hosts:
        your-gpu-node:
          ansible_host: 192.168.1.100
          ansible_user: your-user
          ansible_ssh_private_key_file: ~/.ssh/id_rsa
```

2. Adjust variables in `group_vars/all.yml`:
   - `docker_compose_version`: Docker Compose version
   - `nvidia_driver_version`: NVIDIA driver version (default: "535")
   - `cuda_version`: CUDA version (default: "12.2")
   - `docker_image_name`: Docker image name
   - `docker_registry`: Docker registry URL (if needed)

3. Configure secrets in `group_vars/vault.yml`

## GPU Setup Process

The playbook performs the following steps for GPU setup:

1. **GPU Detection**:
   - Checks for NVIDIA GPU presence using `lspci`
   - Skips all GPU-related tasks if no GPU is found

2. **Driver Status Check**:
   - Verifies if NVIDIA drivers are already installed via `nvidia-smi`
   - Proceeds with installation only if drivers are missing or need update

3. **Secure Boot Check**:
   - Verifies Secure Boot status using `mokutil`
   - Fails with clear message if Secure Boot is enabled

4. **Driver Installation**:
   - Removes any existing NVIDIA drivers
   - Updates package lists
   - Installs specified NVIDIA driver version
   - Holds the driver package to prevent automatic updates
   - Installs nvtop for GPU monitoring

5. **Verification**:
   - Verifies driver installation with `nvidia-smi`
   - Checks driver version and GPU information
   - Confirms package hold status

## Usage

1. Test connection to your nodes:
```bash
ansible all -i inventory/hosts.yml -m ping
```

2. Run the playbook:
```bash
ansible-playbook -i inventory/hosts.yml playbooks/site.yml
```

If you encrypted the vault file:
```bash
ansible-playbook -i inventory/hosts.yml playbooks/site.yml --ask-vault-pass
```

## Troubleshooting

1. **Secure Boot Error**:
   - Message: "Secure Boot is enabled"
   - Solution: Disable Secure Boot in BIOS settings

2. **Driver Installation Fails**:
   - Check `/var/log/dpkg.log` for package installation errors
   - Verify internet connectivity
   - Ensure compatible driver version is specified

3. **No GPU Detected**:
   - Verify GPU is properly seated
   - Check `lspci | grep -i nvidia` output
   - Ensure GPU is supported and powered correctly

4. **Package Lock Issues**:
   - The playbook automatically handles apt/dpkg locks
   - Retries operations up to 5 times with delays
   - Manual fix: Remove lock files if needed (not recommended)

## Post-Installation

After successful installation:

1. Verify GPU status:
```bash
nvidia-smi
```

2. Monitor GPU usage:
```bash
nvtop
```

3. Check driver version:
```bash
nvidia-smi --query-gpu=driver_version --format=csv,noheader
```

## Notes

- The playbook is idempotent and can be run multiple times safely
- GPU setup is skipped automatically on non-GPU nodes
- Driver installation requires a system reboot
- The playbook includes automatic retry mechanisms for package operations
- Keep your vault.yml file secure and never commit it to version control
- Ensure adequate cooling and power for GPU operations
- Consider using NVIDIA container toolkit for Docker GPU support

## Deployment Instructions

### Building the Collection

1. **Prepare the Collection**
   Ensure you have the correct directory structure and all required files:
   ```
   mnl_factory/
   ├── galaxy.yml          # Collection metadata
   ├── README.md
   ├── plugins/
   ├── playbooks/
   └── roles/
   ```

2. **Build the Collection**
   From the root directory of the collection, run:
   ```bash
   ansible-galaxy collection build
   ```
   This will create a tarball like `ratio1-multi_node_launcher-1.0.0.tar.gz`

3. **Install the Collection**
   You can install the collection locally using:
   ```bash
   ansible-galaxy collection install ratio1-multi_node_launcher-1.0.0.tar.gz -p ./collections
   ```

### Using the Collection

1. **Install Dependencies**
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

2. **Configure Your Environment**
   - Copy and edit the inventory file:
     ```bash
     cp inventory/hosts.yml.example inventory/hosts.yml
     ```
   - Update the hosts file with your target nodes
   - Copy and edit the vault file:
     ```bash
     cp group_vars/vault.yml.example group_vars/vault.yml
     ```

3. **Run the Deployment**
   ```bash
   ansible-playbook -i inventory/hosts.yml playbooks/site.yml
   ```

   If using vault encryption:
   ```bash
   ansible-playbook -i inventory/hosts.yml playbooks/site.yml --ask-vault-pass
   ```

### Publishing the Collection (Optional)

To publish the collection to Ansible Galaxy:

1. **Create an Account**
   Sign up at [galaxy.ansible.com](https://galaxy.ansible.com)

2. **Get API Token**
   Generate an API token from your Galaxy profile

3. **Publish**
   ```bash
   ansible-galaxy collection publish ./ratio1-multi_node_launcher-1.0.0.tar.gz --api-key=your_api_token
   ```

## License

MIT

## Authors

- Andrei Damian
- Vitalii Toderian

curl -sSL https://raw.githubusercontent.com/YourUsername/r1setup/main/install.sh | sudo bash
