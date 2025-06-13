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
SETUP_SCRIPTS_DIR="$RATIO1_BASE_DIR/r1_setup"

print_message "\nSetup files will be downloaded to: $SETUP_SCRIPTS_DIR" "$YELLOW"
mkdir -p "$SETUP_SCRIPTS_DIR"

# Change to the setup scripts directory
cd "$SETUP_SCRIPTS_DIR"

# Create temporary directory
TEMP_DIR=$(mktemp -d -p "$SETUP_SCRIPTS_DIR" r1_setup.XXXXXX)
cd "$TEMP_DIR"

# Download setup scripts
print_message "Downloading setup scripts to $SETUP_SCRIPTS_DIR..." "$YELLOW"
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/reformat-cli-fixes/mnl_factory/scripts/1_prerequisites.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/reformat-cli-fixes/mnl_factory/scripts/2_ansible_setup.sh
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/reformat-cli-fixes/mnl_factory/scripts/r1setup
curl -sO https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/reformat-cli-fixes/mnl_factory/scripts/r1setup_wrapper.sh
print_message "Setup scripts downloaded." "$GREEN"

# Copy all scripts to the persistent directory
cp r1setup "$SETUP_SCRIPTS_DIR/"
cp 1_prerequisites.sh "$SETUP_SCRIPTS_DIR/"
cp 2_ansible_setup.sh "$SETUP_SCRIPTS_DIR/"
cp r1setup_wrapper.sh "$SETUP_SCRIPTS_DIR/"

# Make scripts executable in both locations
chmod +x "$SETUP_SCRIPTS_DIR/r1setup"
chmod +x "$SETUP_SCRIPTS_DIR/1_prerequisites.sh"
chmod +x "$SETUP_SCRIPTS_DIR/2_ansible_setup.sh"
chmod +x "$SETUP_SCRIPTS_DIR/r1setup_wrapper.sh"
chmod +x 1_prerequisites.sh 2_ansible_setup.sh r1setup_wrapper.sh

# Install system-wide r1setup command
print_message "Installing system-wide r1setup command..." "$YELLOW"

if sudo ln -sf "$SETUP_SCRIPTS_DIR/r1setup_wrapper.sh" /usr/local/bin/r1setup; then
    print_message "✓ r1setup command installed system-wide (via symbolic link)" "$GREEN"
    print_message "  You can now use 'r1setup' from anywhere in the system" "$GREEN"
else
    print_message "⚠ Failed to install system-wide command. You may need to run this script with sudo privileges." "$YELLOW"
    print_message "  You can still use the script directly from: $SETUP_SCRIPTS_DIR/r1setup" "$YELLOW"
fi

print_message "\nSetup process:" "$GREEN"
print_message "1. Installing prerequisites..." "$YELLOW"
# Run prerequisites from the persistent directory so venv is created there
cd "$SETUP_SCRIPTS_DIR"
sudo ./1_prerequisites.sh

print_message "2. Ansible setup..." "$YELLOW"
./2_ansible_setup.sh

print_message "\n3. Setup complete! You can now use the unified r1setup command:" "$GREEN"
print_message "   • Run 'r1setup' from anywhere to configure nodes and deploy" "$GREEN"
print_message "   • Or use: $SETUP_SCRIPTS_DIR/r1setup" "$GREEN"
print_message "\nNote: The old individual scripts (3_configure.py, 4_run_setup.sh) have been" "$YELLOW"
print_message "replaced by the unified r1setup command with a cleaner interface." "$YELLOW"

# Cleanup temporary directory
cd "$SETUP_SCRIPTS_DIR"
rm -rf "$TEMP_DIR"

print_message "\n🎉 Installation complete!" "$GREEN"
print_message "Run 'r1setup' to get started with node configuration and deployment." "$GREEN"
