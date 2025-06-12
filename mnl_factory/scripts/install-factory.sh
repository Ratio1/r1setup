#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

# Get the current user and their home directory (script is run as user)
CURRENT_USER=$(id -u -n)
CURRENT_HOME=$(eval echo ~$CURRENT_USER) # More reliable way to get home dir

if [ -z "$CURRENT_USER" ] || [ -z "$CURRENT_HOME" ]; then
    print_message "Error: Could not determine the current user or their home directory." "$RED"
    exit 1
fi

print_message "Running setup as user: $CURRENT_USER (Home: $CURRENT_HOME)" "$GREEN"

# Define and create a persistent base directory in the user's home
RATIO1_BASE_DIR="$CURRENT_HOME/.ratio1"
SETUP_SCRIPTS_DIR="$RATIO1_BASE_DIR/r1_setup_scripts"

print_message "\nSetup files will be downloaded to: $SETUP_SCRIPTS_DIR" "$YELLOW"
mkdir -p "$SETUP_SCRIPTS_DIR"

# Change to the setup scripts directory
cd "$SETUP_SCRIPTS_DIR"

# Create temporary directory
TEMP_DIR=$(mkdir mnl_setup)
cd "$TEMP_DIR"

# Download setup scripts
print_message "Downloading setup scripts to $SETUP_SCRIPTS_DIR..." "$YELLOW"
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_ansible_setup.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_configure.py
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/4_run_setup.sh
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
