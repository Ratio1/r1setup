# GPU Node Setup with Ansible

This Ansible playbook automates the setup of GPU nodes with Docker, NVIDIA drivers, and required dependencies.

## Prerequisites

1. Ansible installed on your control node
2. SSH access to target nodes
3. Sudo privileges on target nodes

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
│   ├── docker/        # Docker installation
│   ├── nvidia_drivers/ # NVIDIA drivers installation
│   └── docker_image/  # Docker image management
├── requirements.yml    # Ansible Galaxy requirements
└── .gitignore         # Git ignore patterns
```

## Configuration

1. Edit `inventory/hosts.yml` to add your target nodes
2. Adjust variables in `group_vars/all.yml`:
   - Docker version
   - NVIDIA driver version
   - Docker image name
   - Registry settings (if needed)
3. Configure secrets in `group_vars/vault.yml`

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

## Variables

Key variables in `group_vars/all.yml`:
- `docker_version`: Docker version to install
- `docker_compose_version`: Docker Compose version
- `nvidia_driver_version`: NVIDIA driver version
- `cuda_version`: CUDA version
- `docker_image_name`: Docker image to pull
- `docker_registry`: Docker registry URL (if needed)

Secrets in `group_vars/vault.yml`:
- `docker_registry_username`: Registry username (if needed)
- `docker_registry_password`: Registry password (if needed)
- Additional environment-specific secrets

## Notes

- Ensure your target nodes meet the minimum requirements for NVIDIA drivers
- The playbook requires internet access to download packages
- Make sure to replace the Docker image name with your actual image
- Keep your vault.yml file secure and never commit it to version control 