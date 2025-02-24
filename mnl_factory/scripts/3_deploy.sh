#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

# Get the actual user's home directory
if [ -n "$SUDO_USER" ]; then
    REAL_USER=$SUDO_USER
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_USER=$USER
    REAL_HOME=$HOME
fi

# Get the collection path using the real user's home
COLLECTION_PATH="$REAL_HOME/.ansible/collections/ansible_collections/vitalii_t12/multi_node_launcher"

# Function to check if hosts.yml exists and is not empty
check_hosts_config() {
    local hosts_file="$COLLECTION_PATH/hosts.yml"
    if [ ! -f "$hosts_file" ]; then
        print_message "Error: No hosts configuration found!" "$RED"
        print_message "Please run the configuration script first:" "$YELLOW"
        print_message "python3 2_configure.py" "$NC"
        exit 1
    fi

    if [ ! -s "$hosts_file" ]; then
        print_message "Error: Hosts configuration is empty!" "$RED"
        print_message "Please run the configuration script to set up your hosts:" "$YELLOW"
        print_message "python3 2_configure.py" "$NC"
        exit 1
    fi
}

# Function to display deployment options
show_deployment_menu() {
    print_message "\nDeployment Options:" "$CYAN"
    print_message "1) Full deployment (Docker + NVIDIA drivers + GPU setup)"
    print_message "2) Docker-only deployment"
    print_message "3) Test connection to hosts"
    print_message "4) View current configuration"
    print_message "5) Exit"
    
    read -p "Select an option [1-5]: " choice
    echo
    return $choice
}

# Function to view current configuration
view_configuration() {
    local hosts_file="$COLLECTION_PATH/hosts.yml"
    print_message "\nCurrent Configuration:" "$CYAN"
    print_message "================================" "$CYAN"
    print_message "Configuration file: $hosts_file" "$YELLOW"
    print_message "--------------------------------" "$CYAN"
    
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

# Function to run ansible playbook with proper output
run_playbook() {
    local playbook=$1
    local extra_vars=$2
    
    print_message "\nRunning deployment..." "$YELLOW"
    print_message "================================" "$YELLOW"
    
    if [ -n "$extra_vars" ]; then
        ansible-playbook -i "$COLLECTION_PATH/hosts.yml" "$COLLECTION_PATH/$playbook" --extra-vars "$extra_vars"
    else
        ansible-playbook -i "$COLLECTION_PATH/hosts.yml" "$COLLECTION_PATH/$playbook"
    fi
    
    if [ $? -eq 0 ]; then
        print_message "\nDeployment completed successfully!" "$GREEN"
    else
        print_message "\nDeployment encountered some issues." "$RED"
        print_message "Please check the output above for details." "$YELLOW"
    fi
}

# Main script
print_message "Multi Node Launcher Deployment" "$GREEN"
print_message "=============================" "$GREEN"

# Check if we're in the correct environment
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "/opt/multi-node-launcher/activate_env.sh" ]; then
        print_message "Activating virtual environment..." "$YELLOW"
        source /opt/multi-node-launcher/activate_env.sh
    else
        print_message "Error: Virtual environment not found!" "$RED"
        print_message "Please run the prerequisites script first." "$YELLOW"
        exit 1
    fi
fi

# Check hosts configuration
check_hosts_config

# Main loop
while true; do
    show_deployment_menu
    choice=$?
    
    case $choice in
        1)
            print_message "Starting full deployment..." "$YELLOW"
            run_playbook "playbooks/hosts.yml"
            ;;
        2)
            print_message "Starting Docker-only deployment..." "$YELLOW"
            run_playbook "playbooks/hosts.yml" "skip_gpu=true"
            ;;
        3)
            print_message "Testing connection to hosts..." "$YELLOW"
            run_playbook "playbooks/deploy-config.yml"
            ;;
        4)
            view_configuration
            ;;
        5)
            print_message "Exiting deployment script." "$GREEN"
            exit 0
            ;;
        *)
            print_message "Invalid option. Please try again." "$RED"
            ;;
    esac
done 