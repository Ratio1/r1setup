# Multi Node Launcher

A solution for setting up and managing GPU nodes using Ansible.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Setup](#quick-setup)
- [Initial Setup](#initial-setup)
- [Usage](#usage)
- [Notes](#notes)

## Prerequisites

1. Ansible installed on your control node
2. SSH access to target nodes
3. Sudo privileges on target nodes
4. NVIDIA GPU(s) on target nodes
5. Internet access for package downloads

## Quick Setup

Run the following script to set up your GPU nodes:


```bash
#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

# Create temporary directory
TEMP_DIR=$(mkdir mnl_setup)
cd "$TEMP_DIR"

# Download setup scripts
print_message "Downloading setup scripts..." "$YELLOW"
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_ansible_setup.sh
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_configure.py
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/4_run_setup.sh

# Make scripts executable
chmod +x 1_prerequisites.sh 2_ansible_setup.sh 3_configure.py 4_run_setup.sh

print_message "\nSetup process:" "$GREEN"
print_message "1. Installing prerequisites..." "$YELLOW"
sudo ./1_prerequisites.sh

print_message "2. Ansible setup..." "$YELLOW"
./2_ansible_setup.sh

print_message "\n3. Configuring nodes..." "$YELLOW"
python3 3_configure.py

print_message "\n4. Running setup..." "$YELLOW"
./4_run_setup.sh

```


Save this script as `setup.sh`, make it executable with `chmod +x setup.sh`, and run it with `sudo ./setup.sh`.

## Initial Setup

1. Install required Ansible collections:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

2. Configure your hosts in `inventory/hosts.yml`.

## Usage

1. Test connection to your nodes:
   ```bash
   ansible all -i inventory/hosts.yml -m ping
   ```

2. Run the playbook:
   ```bash
   ansible-playbook -i inventory/hosts.yml playbooks/site.yml
   ```

## Notes

- The playbook is idempotent and can be run multiple times safely.
- Ensure adequate cooling and power for GPU operations.
