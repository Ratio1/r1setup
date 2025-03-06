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

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS_TYPE="macos"
        print_message "Detected macOS system" "$GREEN"
    elif [[ "$OSTYPE" == "linux"* ]]; then
        OS_TYPE="linux"
        print_message "Detected Linux system" "$GREEN"
    else
        print_message "Unsupported OS: $OSTYPE" "$RED"
        exit 1
    fi
}

# Get the actual user's home directory and username when running with sudo
get_real_user() {
    if [ -n "$SUDO_USER" ]; then
        REAL_USER=$SUDO_USER
        if [[ "$OS_TYPE" == "macos" ]]; then
            REAL_HOME=$(dscl . -read /Users/"$SUDO_USER" NFSHomeDirectory | awk '{print $2}')
        else
            REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        fi
    else
        REAL_USER=$USER
        REAL_HOME=$HOME
    fi
    
    print_message "Setting up Multi Node Launcher as user: $REAL_USER" "$GREEN"
}

# Get group of the real user
get_real_group() {
    if [[ "$OS_TYPE" == "macos" ]]; then
        REAL_GROUP=$(id -gn "$REAL_USER")
    else
        REAL_GROUP=$(id -gn "$REAL_USER")
    fi
}

# Configure sudoers to avoid password prompts
setup_sudoers() {
    if [[ "$OS_TYPE" == "macos" ]]; then
        # Check if /etc/sudoers.d exists, create if not
        if [ ! -d /etc/sudoers.d ]; then
            mkdir -p /etc/sudoers.d
            echo "#includedir /etc/sudoers.d" >> /etc/sudoers
        fi
        
        echo "$REAL_USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/temp_nopasswd
        chmod 440 /etc/sudoers.d/temp_nopasswd
    else
        echo "$REAL_USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/temp_nopasswd
        chmod 440 /etc/sudoers.d/temp_nopasswd
    fi
}

# Clean up temporary sudoers entry
cleanup_sudoers() {
    rm -f /etc/sudoers.d/temp_nopasswd
}

# Main setup function
main() {
    detect_os
    get_real_user
    get_real_group
    
    # Create temporary directory with correct ownership
    TEMP_DIR="mnl_setup"
    mkdir -p "$TEMP_DIR"
    chown "$REAL_USER":"$REAL_GROUP" "$TEMP_DIR"
    cd "$TEMP_DIR"
    
    # Download setup scripts as the real user
    print_message "Downloading setup scripts..." "$YELLOW"
    sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
    sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_ansible_setup.sh
    sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_configure.py
    sudo -u "$REAL_USER" curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/4_run_setup.sh
    
    # Make scripts executable but maintain user ownership
    chmod +x 1_prerequisites.sh 2_ansible_setup.sh 4_run_setup.sh
    chown "$REAL_USER":"$REAL_GROUP" 1_prerequisites.sh 2_ansible_setup.sh 3_configure.py 4_run_setup.sh
    
    # Modify first script to support macOS if needed
    if [[ "$OS_TYPE" == "macos" ]]; then
        print_message "Adapting scripts for macOS compatibility..." "$YELLOW"
        # Add macOS compatibility to prerequisites script
        sed -i.bak 's/apt-get install/brew install/g' 1_prerequisites.sh
        sed -i.bak 's/apt-add-repository/echo "brew tap"/g' 1_prerequisites.sh
        sed -i.bak 's/dnf install/brew install/g' 1_prerequisites.sh
    fi
    
    # Configure sudoers to avoid password prompts
    setup_sudoers
    
    print_message "\nSetup process:" "$GREEN"
    print_message "1. Installing prerequisites..." "$YELLOW"
    # Pass environment variables to the prerequisites script
    export REAL_USER REAL_HOME OS_TYPE
    ./1_prerequisites.sh
    
    print_message "2. Ansible setup..." "$YELLOW"
    # Run as regular user without sudo - ansible setup should be done by a regular user
    print_message "Dropping to regular user for Ansible setup..." "$YELLOW"
    su - "$REAL_USER" -c "cd $(pwd) && ./2_ansible_setup.sh"
    
    print_message "\n3. Configuring nodes..." "$YELLOW"
    # Drop privileges completely - this script should run as normal user
    print_message "Dropping to regular user for configuration..." "$YELLOW"
    su - "$REAL_USER" -c "cd $(pwd) && python3 3_configure.py"
    
    print_message "\n4. Running setup..." "$YELLOW"
    # Run as regular user without sudo - this script should also run without elevated privileges
    print_message "Dropping to regular user for setup..." "$YELLOW"
    su - "$REAL_USER" -c "cd $(pwd) && ./4_run_setup.sh"
    
    # Clean up the temporary sudoers entry
    cleanup_sudoers
    
    print_message "\nSetup completed!" "$GREEN"
}

# Run the main function
main
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
- For macOS users: This setup uses Homebrew for package management, so make sure Homebrew is installed first.
