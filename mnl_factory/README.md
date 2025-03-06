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
BLUE='\033[0;34m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

# Debug message function
debug() {
    echo -e "${BLUE}[DEBUG] $1${NC}"
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

# Set installation directories based on OS
set_install_dirs() {
    # Use user's home directory for everything
    INSTALL_DIR="$REAL_HOME/multi-node-launcher"
    FACTORY_DIR="$REAL_HOME/factory"
    
    # Use a simpler path for the Ansible collection
    ANSIBLE_COLLECTION_DIR="$REAL_HOME/ratio1"
    
    # Create these directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$FACTORY_DIR"
    mkdir -p "$ANSIBLE_COLLECTION_DIR"
    
    # Set ownership
    chown -R "$REAL_USER:$REAL_GROUP" "$INSTALL_DIR"
    chown -R "$REAL_USER:$REAL_GROUP" "$FACTORY_DIR"
    chown -R "$REAL_USER:$REAL_GROUP" "$ANSIBLE_COLLECTION_DIR"
    
    # Collection path (where hosts.yml will be stored by the collection)
    COLLECTION_PATH="$ANSIBLE_COLLECTION_DIR/multi_node_launcher"
    
    debug "Installation directory: $INSTALL_DIR"
    debug "Factory directory: $FACTORY_DIR"
    debug "Ansible collection directory: $ANSIBLE_COLLECTION_DIR"
    debug "Collection path: $COLLECTION_PATH"
    
    # Export these for other scripts
    export INSTALL_DIR FACTORY_DIR ANSIBLE_COLLECTION_DIR COLLECTION_PATH
}

# Main setup function
main() {
    detect_os
    get_real_user
    get_real_group
    set_install_dirs
    
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
    
    # Modify the Python configuration script to support custom paths
    print_message "Patching Python configuration script..." "$YELLOW"
    cat > modify_configure.py << 'EOF'
#!/usr/bin/env python3
import sys
import re

# Read the original file
with open('3_configure.py', 'r') as f:
    content = f.read()

# Add command line argument parsing
argparse_import = "import argparse"
if argparse_import not in content:
    content = content.replace("import os", "import os\nimport argparse")

# Add argument parsing function near the main function
parser_setup = """
def parse_arguments():
    parser = argparse.ArgumentParser(description='Configure Multi Node Launcher')
    parser.add_argument('--collection-path', required=False, 
                        help='Path to the Ansible collection directory')
    parser.add_argument('--factory-dir', required=False,
                        help='Path to the factory directory')
    return parser.parse_args()
"""

# Find the right place to add the function
if "def parse_arguments():" not in content:
    content = content.replace("def main():", parser_setup + "\ndef main():")

# Modify the main function to use arguments
if "args = parse_arguments()" not in content:
    main_modification = """def main():
    args = parse_arguments()
    config_manager = ConfigManager()
    
    # Apply command line arguments if provided
    if args.collection_path:
        config_manager.collection_path = args.collection_path
    if args.factory_dir:
        config_manager.factory_dir = args.factory_dir"""
    
    content = content.replace("def main():\n    config_manager = ConfigManager()", main_modification)

# Make sure the ConfigManager init can handle custom paths
if "self.factory_dir = args.factory_dir" not in content:
    constructor_mod = """    def __init__(self):
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'purple': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'end': '\033[0m'
        }
        
        # Default paths - will be overridden by command line args if provided
        self.os_type = platform.system().lower()
        self.base_dir = os.path.expanduser("~/multi-node-launcher")
        self.factory_dir = os.path.expanduser("~/factory")
        self.collection_path = None  # Will be set via command line"""
        
    content = re.sub(r"    def __init__\(\):\s+self\.colors = \{.*?'end': '\\033\[0m'\s+\}", 
                     constructor_mod, content, flags=re.DOTALL)

# Write the modified file
with open('3_configure.py', 'w') as f:
    f.write(content)

print("Configuration script patched successfully!")
EOF

    # Make the patch script executable and run it
    chmod +x modify_configure.py
    sudo -u "$REAL_USER" python3 modify_configure.py
    
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
    # Pass the custom collection path to use ~/ratio1 instead of ~/.ansible and factory in home directory
    su - "$REAL_USER" -c "cd $(pwd) && ANSIBLE_COLLECTIONS_PATH=$REAL_HOME ./2_ansible_setup.sh --collection-path=$ANSIBLE_COLLECTION_DIR --factory-dir=$FACTORY_DIR"
    
    print_message "\n3. Configuring nodes..." "$YELLOW"
    # Drop privileges completely - this script should run as normal user
    print_message "Dropping to regular user for configuration..." "$YELLOW"
    # Use the collection path for configuration without trying to override the hosts file location
    su - "$REAL_USER" -c "cd $(pwd) && python3 3_configure.py --collection-path=$COLLECTION_PATH --factory-dir=$FACTORY_DIR"
    
    print_message "\n4. Running setup..." "$YELLOW"
    # Run as regular user without sudo - this script should also run without elevated privileges
    print_message "Dropping to regular user for setup..." "$YELLOW"
    # Run from the factory directory with environment variables pointing to the collection
    su - "$REAL_USER" -c "cd $(pwd) && ANSIBLE_COLLECTIONS_PATH=$ANSIBLE_COLLECTION_DIR ./4_run_setup.sh --factory-dir=$FACTORY_DIR"
    
    # Clean up the temporary sudoers entry
    cleanup_sudoers
    
    print_message "\nSetup completed!" "$GREEN"
    print_message "\nYour directory structure:" "$GREEN"
    print_message "Main installation: $INSTALL_DIR" "$GREEN"
    print_message "Factory directory: $FACTORY_DIR" "$GREEN"
    print_message "Ansible collection: $COLLECTION_PATH" "$GREEN"
    print_message "Hosts file will be in: $COLLECTION_PATH/hosts.yml" "$GREEN"
    print_message "\nTo use the Multi Node Launcher, run:" "$YELLOW"
    print_message "cd $FACTORY_DIR && ansible-playbook -i $COLLECTION_PATH/hosts.yml playbooks/site.yml" "$NC"
}

# Run the main function
main
```