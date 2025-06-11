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
    if [[ "$OS_TYPE" == "macos" ]]; then
        ANSIBLE_DIR="$REAL_HOME/.ansible"
    else
        ANSIBLE_DIR="$REAL_HOME/.ansible"
    fi
    
    COLLECTION_PATH="$ANSIBLE_DIR/collections/ansible_collections/ratio1/multi_node_launcher"
}

# Create required directories
create_dirs() {
    # Create Ansible directory structure
    mkdir -p "$ANSIBLE_DIR/collections"
    # Ensure the real user owns the directory structure so that subsequent commands executed as
    # this user (e.g. `ansible-galaxy collection install`) have the correct permissions.
    chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$ANSIBLE_DIR"
}

# Install Ansible collection
install_collection() {
    print_message "Installing Multi Node Launcher collection..." "$YELLOW"
    
    # Install the collection
    sudo -u "$REAL_USER" env HOME="$REAL_HOME" ansible-galaxy collection install ratio1.multi_node_launcher --collections-path "$ANSIBLE_DIR/collections" --force --upgrade
    
    # Verify collection installation
    COLLECTION_INFO=$(sudo -u "$REAL_USER" env HOME="$REAL_HOME" ansible-galaxy collection list --collections-path "$ANSIBLE_DIR/collections" 2>/dev/null | grep "ratio1.multi_node_launcher" || true)
    if [ -z "$COLLECTION_INFO" ]; then
        print_message "Failed to detect installed collection" "$RED"
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