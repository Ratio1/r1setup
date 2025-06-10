#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

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
SETUP_SCRIPTS_DIR="$RATIO1_BASE_DIR/mnl_setup_scripts"

print_message "\nSetup files will be downloaded to: $SETUP_SCRIPTS_DIR" "$YELLOW"
mkdir -p "$SETUP_SCRIPTS_DIR"

# Change to the setup scripts directory
cd "$SETUP_SCRIPTS_DIR"

# Download setup scripts
print_message "Downloading setup scripts to $SETUP_SCRIPTS_DIR..." "$YELLOW"
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_ansible_setup.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_configure.py
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/4_run_setup.sh

# Make scripts executable
chmod +x 1_prerequisites.sh 2_ansible_setup.sh 3_configure.py 4_run_setup.sh

print_message "\nSetup process starting in $SETUP_SCRIPTS_DIR:" "$GREEN"
print_message "1. Installing prerequisites (will request sudo if needed)..." "$YELLOW"
sudo ./1_prerequisites.sh # This script handles sudo internally for package management.

print_message "\n2. Ansible setup (running as $CURRENT_USER)..." "$YELLOW"
./2_ansible_setup.sh # Runs as the current user

# Define Python executable from the venv created in 1_prerequisites.sh
# $SETUP_SCRIPTS_DIR is the current working directory here.
PYTHON_IN_VENV="./mnl_venv/bin/python3"

print_message "\n3. Configuring nodes (running as $CURRENT_USER using $PYTHON_IN_VENV)..." "$YELLOW"
if [ ! -f "$PYTHON_IN_VENV" ]; then
    print_message "Error: Python interpreter not found in virtual environment: $PYTHON_IN_VENV" "$RED"
    print_message "Please check 1_prerequisites.sh for errors." "$RED"
    exit 1
fi
"$PYTHON_IN_VENV" 3_configure.py # Runs as the current user, using python from venv

print_message "\n4. Running setup (running as $CURRENT_USER)..." "$YELLOW"
./4_run_setup.sh # Runs as the current user

print_message "\nInstallation factory setup complete." "$GREEN"
print_message "All setup scripts are located in: $SETUP_SCRIPTS_DIR" "$GREEN"
print_message "Ansible configurations will be stored under: $RATIO1_BASE_DIR/ansible_config" "$GREEN"
print_message "You can re-run specific steps from $SETUP_SCRIPTS_DIR if needed." "$GREEN"
