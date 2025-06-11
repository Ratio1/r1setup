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
print_message "Downloading setup scripts to $SETUP_SCRIPTS_DIR..." "$YELLOW"
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/gpu-fixes/mnl_factory/scripts/1_prerequisites.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/gpu-fixes/mnl_factory/scripts/2_ansible_setup.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/gpu-fixes/mnl_factory/scripts/3_configure.py
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/gpu-fixes/mnl_factory/scripts/4_run_setup.sh
print_message "Setup scripts downloaded." "$GREEN"

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
