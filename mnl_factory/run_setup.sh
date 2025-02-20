#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${YELLOW}[*] $1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}[+] $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}[-] $1${NC}"
}

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run with sudo"
    exit 1
fi

# Current directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

print_status "Installing prerequisites..."

# Install Ansible if not present
if ! command -v ansible &> /dev/null; then
    print_status "Installing Ansible..."
    apt update
    apt install -y ansible
    print_success "Ansible installed successfully"
else
    print_success "Ansible is already installed"
fi

# Install required Ansible collections
print_status "Installing required Ansible collections..."
ansible-galaxy collection install -r "$SCRIPT_DIR/requirements.yml"
print_success "Ansible collections installed successfully"

# Test connection
print_status "Testing connection to target machine..."
if ansible-playbook -i "$SCRIPT_DIR/inventory/hosts.yml" "$SCRIPT_DIR/playbooks/test.yml"; then
    print_success "Connection test successful"
else
    print_error "Connection test failed"
    exit 1
fi

# Ask for confirmation before proceeding
echo
print_status "This will install Docker, NVIDIA drivers, and set up the environment."
read -p "Do you want to continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Setup cancelled"
    exit 0
fi

# Run the main playbook
print_status "Running main playbook..."
if ansible-playbook -i "$SCRIPT_DIR/inventory/hosts.yml" "$SCRIPT_DIR/playbooks/site.yml"; then
    print_success "Setup completed successfully"
else
    print_error "Setup failed"
    exit 1
fi

# Print final status
echo
print_success "Installation process completed!"
echo -e "${GREEN}You can verify the installation by:"
echo "1. SSH into your machine: ssh vv@192.168.0.105"
echo "2. Check Docker: docker --version"
echo "3. Check NVIDIA drivers: nvidia-smi"
echo -e "4. Check NVIDIA Docker: docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi${NC}" 