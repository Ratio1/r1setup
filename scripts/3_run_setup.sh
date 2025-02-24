#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging levels
declare -A LOG_LEVELS=( ["DEBUG"]=0 ["INFO"]=1 ["WARNING"]=2 ["ERROR"]=3 )
LOG_LEVEL=${LOG_LEVEL:-"INFO"} # Default to INFO if not set

# Convert LOG_LEVEL to uppercase
LOG_LEVEL=${LOG_LEVEL^^}

# Validate LOG_LEVEL
if [[ ! "${LOG_LEVELS[$LOG_LEVEL]+exists}" ]]; then
    echo "Invalid LOG_LEVEL: $LOG_LEVEL. Using INFO."
    LOG_LEVEL="INFO"
fi

# Logging functions
log() {
    local level=$1
    local message=$2
    local color=$3
    
    # Check if we should log this message based on level
    if [ "${LOG_LEVELS[$level]}" -ge "${LOG_LEVELS[$LOG_LEVEL]}" ]; then
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        echo -e "${color}[${timestamp}] [${level}] ${message}${NC}"
    fi
}

debug() {
    log "DEBUG" "$1" "$BLUE"
}

info() {
    log "INFO" "$1" "$GREEN"
}

warning() {
    log "WARNING" "$1" "$YELLOW"
}

error() {
    log "ERROR" "$1" "$RED"
}

# Get the actual user's home directory
if [ -n "$SUDO_USER" ]; then
    REAL_USER=$SUDO_USER
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_USER=$USER
    REAL_HOME=$HOME
fi

debug "Real user: $REAL_USER"
debug "Real home: $REAL_HOME"

# Get the collection path using the real user's home
COLLECTION_PATH="$REAL_HOME/.ansible/collections/ansible_collections/vitalii_t12/multi_node_launcher"
debug "Collection path: $COLLECTION_PATH"

# Function to check if hosts.yml exists and is not empty
check_hosts_config() {
    local hosts_file="$COLLECTION_PATH/hosts.yml"
    debug "Checking hosts file: $hosts_file"
    
    if [ ! -f "$hosts_file" ]; then
        debug "Hosts file not found"
        error "No hosts configuration found!"
        warning "Please run the configuration script first:"
        info "python3 2_configure.py"
        exit 1
    fi

    if [ ! -s "$hosts_file" ]; then
        debug "Hosts file is empty"
        error "Hosts configuration is empty!"
        warning "Please run the configuration script to set up your hosts:"
        info "python3 2_configure.py"
        exit 1
    fi
    
    debug "Hosts file exists and is not empty"
}

# Function to verify ansible installation and collection
verify_ansible() {
    debug "Verifying Ansible installation"
    if ! command -v ansible &> /dev/null; then
        error "Ansible is not installed!"
        exit 1
    fi
    debug "Ansible is installed"

    debug "Verifying Ansible collection"
    if ! ansible-galaxy collection list | grep -q "vitalii_t12.multi_node_launcher"; then
        error "Required Ansible collection is not installed!"
        exit 1
    fi
    debug "Required collection is installed"
}

# Function to display deployment options
show_deployment_menu() {
    print_status "Deployment Options:"
    echo "1) Full deployment (Docker + NVIDIA drivers + GPU setup)"
    echo "2) Docker-only deployment"
    echo "3) Test connection to hosts"
    echo "4) View current configuration"
    echo "5) Exit"
    
    read -p "Select an option [1-5]: " choice
    echo
    return $choice
}

# Function to view current configuration
view_configuration() {
    local hosts_file="$COLLECTION_PATH/hosts.yml"
    print_status "Current Configuration"
    echo "================================"
    print_success "Configuration file: $hosts_file"
    echo "--------------------------------"
    
    # Use Python to read and display YAML without sensitive information
    python3 -c '
import yaml
import sys

def mask_sensitive(value):
    return "********" if any(k in str(value).lower() for k in ["password", "key"]) else value

with open(sys.argv[1]) as f:
    config = yaml.safe_load(f)
    if config and "all" in config and "children" in config["all"]:
        hosts = config["all"]["children"]["gpu_nodes"]["hosts"]
        for host_name, host_config in hosts.items():
            print(f"\nHost: {host_name}")
            for key, value in host_config.items():
                print(f"  {key}: {mask_sensitive(value)}")
    ' "$hosts_file"
    
    echo
    read -p "Press Enter to continue..."
}

# Function to run ansible playbook with debug info
run_playbook() {
    local playbook=$1
    local extra_vars=$2
    
    info "Running deployment..."
    info "================================"
    
    debug "Running playbook: $playbook"
    debug "Inventory file: $COLLECTION_PATH/hosts.yml"
    debug "Extra vars: $extra_vars"
    
    # Check if playbook exists
    if [ ! -f "$COLLECTION_PATH/playbooks/$playbook" ]; then
        error "Playbook not found: $COLLECTION_PATH/playbooks/$playbook"
        debug "Available playbooks:"
        ls -l "$COLLECTION_PATH/playbooks/" 2>/dev/null || echo "No playbooks directory found"
        exit 1
    fi

    local ansible_cmd="ansible-playbook -i $COLLECTION_PATH/hosts.yml $COLLECTION_PATH/playbooks/$playbook"
    if [ -n "$extra_vars" ]; then
        ansible_cmd="$ansible_cmd --extra-vars \"$extra_vars\""
    fi
    
    # Add verbose flags based on log level
    case $LOG_LEVEL in
        "DEBUG")
            ansible_cmd="$ansible_cmd -vvv"
            ;;
        "INFO")
            ansible_cmd="$ansible_cmd -v"
            ;;
    esac
    
    debug "Running command: $ansible_cmd"
    
    if eval "$ansible_cmd"; then
        info "Deployment completed successfully!"
    else
        local exit_code=$?
        error "Deployment encountered some issues."
        warning "Please check the output above for details."
        debug "Ansible exit code: $exit_code"
        exit 1
    fi
}

# Main script
info "Multi Node Launcher Deployment"
info "============================="

debug "Checking virtual environment"
# Check if we're in the correct environment
if [ -z "$VIRTUAL_ENV" ]; then
    debug "No virtual environment active"
    if [ -f "/opt/multi-node-launcher/activate_env.sh" ]; then
        info "Activating virtual environment..."
        debug "Activating from: /opt/multi-node-launcher/activate_env.sh"
        source /opt/multi-node-launcher/activate_env.sh
    else
        debug "Virtual environment activation script not found"
        error "Virtual environment not found!"
        warning "Please run the prerequisites script first."
        exit 1
    fi
fi

debug "Virtual environment active: $VIRTUAL_ENV"

# Verify ansible installation
verify_ansible

# Check hosts configuration
check_hosts_config

# Main loop
while true; do
    info "\nDeployment Options:"
    echo "1) Full deployment (Docker + NVIDIA drivers + GPU setup)"
    echo "2) Docker-only deployment"
    echo "3) Test connection to hosts"
    echo "4) View current configuration"
    echo "5) Exit"
    
    read -p "Select an option [1-5]: " choice
    echo
    debug "User selected option: $choice"
    
    case $choice in
        1)
            info "Starting full deployment..."
            run_playbook "site.yml"
            ;;
        2)
            info "Starting Docker-only deployment..."
            run_playbook "site.yml" "skip_gpu=true"
            ;;
        3)
            info "Testing connection to hosts..."
            run_playbook "deploy-config.yml"
            ;;
        4)
            view_configuration
            ;;
        5)
            info "Exiting deployment script."
            exit 0
            ;;
        *)
            error "Invalid option. Please try again."
            ;;
    esac
done 