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

# Get the actual user's home directory and username when running with sudo
if [ -n "$SUDO_USER" ]; then
    REAL_USER=$SUDO_USER
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_USER=$USER
    REAL_HOME=$HOME
fi

print_message "Setting up Multi Node Launcher as user: $REAL_USER" "$GREEN"

# Create temporary directory with correct ownership
TEMP_DIR="mnl_setup"
mkdir -p "$TEMP_DIR"
chown "$REAL_USER":"$(id -gn "$REAL_USER")" "$TEMP_DIR"
cd "$TEMP_DIR"

# Download setup scripts as the real user
print_message "Downloading setup scripts..." "$YELLOW"
sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_ansible_setup.sh
sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_configure.py
sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/4_run_setup.sh

# Make scripts executable but maintain user ownership
chmod +x 1_prerequisites.sh 2_ansible_setup.sh 4_run_setup.sh
chown "$REAL_USER":"$(id -gn "$REAL_USER")" 1_prerequisites.sh 2_ansible_setup.sh 3_configure.py 4_run_setup.sh

# Add an entry to sudoers to avoid password prompts for this user temporarily
echo "$REAL_USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/temp_nopasswd
chmod 440 /etc/sudoers.d/temp_nopasswd

print_message "\nSetup process:" "$GREEN"
print_message "1. Installing prerequisites..." "$YELLOW"
# Pass REAL_USER as an environment variable to the prerequisites script
export REAL_USER REAL_HOME
./1_prerequisites.sh

print_message "2. Ansible setup..." "$YELLOW"
# Run as real user, who now has NOPASSWD sudo privileges
sudo -E -u "$REAL_USER" ./2_ansible_setup.sh

print_message "\n3. Configuring nodes..." "$YELLOW"
# Run as real user
sudo -E -u "$REAL_USER" python3 3_configure.py

print_message "\n4. Running setup..." "$YELLOW"
# Run as real user
sudo -E -u "$REAL_USER" ./4_run_setup.sh

# Clean up the temporary sudoers entry
rm -f /etc/sudoers.d/temp_nopasswd

print_message "\nSetup completed!" "$GREEN"
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
