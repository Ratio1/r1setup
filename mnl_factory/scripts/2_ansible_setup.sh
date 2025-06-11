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
        # Detect Linux distribution
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            OS_NAME=$NAME
        else
            print_message "Unable to determine Linux distribution" "$YELLOW"
            OS_NAME="Unknown Linux"
        fi
    else
        print_message "Unsupported OS: $OSTYPE" "$RED"
        exit 1
    fi
}

# Get the actual user's home directory and username
get_user_info() {
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
}

# Set installation directories based on OS
set_install_dirs() {
    # REAL_HOME is the actual user's home directory
    local ratio1_base_dir_for_ansible="$REAL_HOME/.ratio1"
    # ANSIBLE_DIR will be the root for our Ansible specific configurations
    ANSIBLE_DIR="$ratio1_base_dir_for_ansible/ansible_config"
    
    # Collection path within our new ANSIBLE_DIR structure
    COLLECTION_PATH="$ANSIBLE_DIR/collections/ansible_collections/ratio1/multi_node_launcher"
}

# Create required directories
create_dirs() {
    # Create Ansible directory structure within $ANSIBLE_DIR
    # This will create $REAL_HOME/.ratio1/ansible_config/collections if it doesn't exist
    mkdir -p "$ANSIBLE_DIR/collections"
}

# Install Ansible collection
install_collection() {
    print_message "Installing Multi Node Launcher collection into $ANSIBLE_DIR/collections..." "$YELLOW"
    
    # Ensure the target collections directory exists (it should be created by create_dirs)
    mkdir -p "$ANSIBLE_DIR/collections"

    # Install the collection into the specified path
    # We use ANSIBLE_COLLECTIONS_PATHS to tell ansible-galaxy where to install and look for collections.
    if sudo -u "$REAL_USER" env HOME="$REAL_HOME" ANSIBLE_COLLECTIONS_PATHS="$ANSIBLE_DIR/collections" ansible-galaxy collection install ratio1.multi_node_launcher --force --upgrade; then
        print_message "Ansible collection installation command executed." "$GREEN"
    else
        print_message "Ansible collection installation command failed." "$RED"
        exit 1
    fi
    
    # Verify collection installation in the new path
    COLLECTION_INFO=$(sudo -u "$REAL_USER" env HOME="$REAL_HOME" ANSIBLE_COLLECTIONS_PATHS="$ANSIBLE_DIR/collections" ansible-galaxy collection list 2>/dev/null | grep "ratio1.multi_node_launcher" || true)
    if [ -z "$COLLECTION_INFO" ]; then
        print_message "Failed to detect installed collection in $ANSIBLE_DIR/collections." "$RED"
        print_message "Attempted to list collections from: $ANSIBLE_DIR/collections" "$YELLOW"
        exit 1
    fi
    
    # Extract version and path from collection info
    COLLECTION_VER=$(echo "$COLLECTION_INFO" | awk '{print $2}')
    
    if [ ! -d "$COLLECTION_PATH" ]; then
        print_message "Collection directory not found at: $COLLECTION_PATH" "$RED"
        exit 1
    fi
    
    print_message "Collection ratio1.multi_node_launcher v$COLLECTION_VER installed successfully" "$GREEN"
    print_message "Collection path: $COLLECTION_PATH" "$GREEN"
}

# Create factory directory and templates

# Set ownership and permissions
set_ownership() {

    # Add environment setup to the real user's .bashrc if not already present
    SHELL_RC_PATH=""
    if [[ "$OS_TYPE" == "macos" ]]; then
        # Check for zsh (default in newer macOS) or bash
        if [ -f "$REAL_HOME/.zshrc" ]; then
            SHELL_RC_PATH="$REAL_HOME/.zshrc"
        else
            SHELL_RC_PATH="$REAL_HOME/.bash_profile"
        fi
    else
        SHELL_RC_PATH="$REAL_HOME/.bashrc"
    fi
    
    if ! grep -q "$BASHRC_ENTRY" "$SHELL_RC_PATH"; then
        echo "$BASHRC_ENTRY" >> "$SHELL_RC_PATH"
    fi
}

# Print next steps
print_next_steps() {
    print_message "\nInstallation completed successfully!" "$GREEN"
    print_message "\nNext steps:" "$YELLOW"
    print_message "1. Run the configuration script:" "$NC"
    print_message "   python3 3_configure.py" "$NC"
    print_message "2. After configuration, deploy with:" "$NC"
    print_message "   ansible-playbook deploy.yml" "$NC"
}

# Main function
main() {
    detect_os
    get_user_info
    set_install_dirs
    create_dirs
    install_collection
    set_ownership
    print_next_steps
}

# Run the main function
main