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

# Set Ansible environment variables to use the real user's home directory
export ANSIBLE_CONFIG="$REAL_HOME/.ansible.cfg"
export ANSIBLE_COLLECTIONS_PATH="$REAL_HOME/.ansible/collections"
export ANSIBLE_HOME="$REAL_HOME/.ansible"

# Get the collection path using the real user's home
COLLECTION_PATH="$REAL_HOME/.ansible/collections/ansible_collections/ratio1/multi_node_launcher"
debug "Collection path: $COLLECTION_PATH"

# Add this near the top of the script, after the color definitions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Function to check if hosts.yml exists and is not empty
check_hosts_config() {
    local hosts_file="$COLLECTION_PATH/hosts.yml"
    debug "Checking hosts file: $hosts_file"

    if [ ! -f "$hosts_file" ]; then
        debug "Hosts file not found"
        print_error "No hosts configuration found!"
        print_status "Please run the configuration script first:"
        echo "python3 3_configure.py"
        exit 1
    fi

    if [ ! -s "$hosts_file" ]; then
        debug "Hosts file is empty"
        print_error "Hosts configuration is empty!"
        print_status "Please run the configuration script to set up your hosts:"
        echo "python3 3_configure.py"
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
    if ! ANSIBLE_CONFIG=$ANSIBLE_CONFIG ANSIBLE_COLLECTIONS_PATH=$ANSIBLE_COLLECTIONS_PATH ANSIBLE_HOME=$ANSIBLE_HOME ansible-galaxy collection list | grep -q "ratio1.multi_node_launcher"; then
        error "Required Ansible collection is not installed!"
        exit 1
    fi
    debug "Required collection is installed"
}

# Function to parse node info output and extract addresses
parse_node_info() {
    local output_file="/tmp/node_info_output.txt"
    local show_only=${1:-"true"}

    # Run the playbook and capture output
    ANSIBLE_STDOUT_CALLBACK=yaml ANSIBLE_CONFIG=$ANSIBLE_CONFIG ANSIBLE_COLLECTIONS_PATH=$ANSIBLE_COLLECTIONS_PATH ANSIBLE_HOME=$ANSIBLE_HOME ansible-playbook -i "$COLLECTION_PATH/hosts.yml" "$COLLECTION_PATH/playbooks/get_node_info.yml" > "$output_file" 2>&1

    debug "Parsing node info from: $output_file"

    # Parse the output using awk
    awk -v show="$show_only" -v collection_path="$COLLECTION_PATH" '
    BEGIN {
        host="";
        in_stdout_lines=0;
        if (show == "true") {
            printf "\n%-20s %-15s %-45s %-42s\n", "HOST", "IP", "ADDRESS", "ETH ADDRESS"
            printf "%-20s %-15s %-45s %-42s\n", "--------------------", "---------------", "---------------------------------------------", "------------------------------------------"
        }
    }
    /^ok: \[.*\] =>/ {
        match($0, /\[(.*)\]/)
        host=substr($0, RSTART+1, RLENGTH-2)
        # Extract IP if the host is an IP address
        if (host ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/) {
            ip = host
        } else {
            # Try to get IP from ansible_host in inventory
            cmd = "grep -A1 \"" host ":\" " collection_path "/hosts.yml | grep ansible_host | cut -d: -f2"
            cmd | getline ip
            close(cmd)
            gsub(/[[:space:]]/, "", ip)
        }
    }
    /"address": / {
        if (in_stdout_lines) {
            match($0, /"address": "([^"]*)"/)
            address=substr($0, RSTART+11, RLENGTH-12)
            gsub(/"/, "", address)  # Remove any remaining quotes
        }
    }
    /"eth_address": / {
        if (in_stdout_lines) {
            match($0, /"eth_address": "([^"]*)"/)
            eth_address=substr($0, RSTART+15, RLENGTH-16)
            gsub(/"/, "", eth_address)  # Remove any remaining quotes
            if (show == "true") {
                printf "%-20s %-15s %-45s %-42s\n", host, ip, address, eth_address
            } else {
                printf "%s,%s,%s,%s\n", host, ip, address, eth_address
            }
        }
    }
    /node_info.stdout_lines:/ { in_stdout_lines=1 }
    /skipping: \[.*\]/ { in_stdout_lines=0 }
    ' "$output_file"

    # Clean up
    rm -f "$output_file"

    if [ "$show_only" = "true" ]; then
        echo
        read -p "Press Enter to continue..."
    fi
}

# Function to save node info to CSV
save_node_info_csv() {
    local csv_file="node_info_$(date +%Y%m%d_%H%M%S).csv"

    print_status "Saving node information to CSV..."

    # Add header to CSV file
    echo "Host,IP,Address,ETH_Address" > "$csv_file"

    # Call parse_node_info with show_only=false to get CSV format
    parse_node_info "false" >> "$csv_file"

    if [ $? -eq 0 ]; then
        print_success "Node information saved to: $csv_file"
        echo
        read -p "Press Enter to continue..."
    else
        print_error "Failed to save node information"
        rm -f "$csv_file"
        exit 1
    fi
}

# Function to display deployment options
show_deployment_menu() {
    print_status "Deployment Options:"
    echo "1) Full deployment (Docker + NVIDIA drivers + GPU setup) - Installs all necessary components for a complete setup."
    echo "2) Docker-only deployment - Installs only Docker without GPU setup."
    echo "3) Test connection to hosts - Verifies connectivity to all specified hosts in the inventory."
    echo "4) Get nodes information - Retrieves detailed information about the nodes in the setup."
    echo "5) Get nodes addresses - Extracts and displays the IP addresses of the nodes."
    echo "6) Save nodes addresses to CSV - Saves the extracted node addresses into a CSV file for easy access."
    echo "7) View current configuration - Displays the current configuration settings without sensitive information."
    echo "8) Exit - Terminates the deployment script."
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
    debug "Using Ansible home: $ANSIBLE_HOME"

    # Check if playbook exists
    if [ ! -f "$COLLECTION_PATH/playbooks/$playbook" ]; then
        error "Playbook not found: $COLLECTION_PATH/playbooks/$playbook"
        debug "Available playbooks:"
        ls -l "$COLLECTION_PATH/playbooks/" 2>/dev/null || echo "No playbooks directory found"
        exit 1
    fi

    local ansible_cmd="ANSIBLE_ROLES_PATH=$COLLECTION_PATH/roles ANSIBLE_CONFIG=$ANSIBLE_CONFIG ANSIBLE_COLLECTIONS_PATH=$ANSIBLE_COLLECTIONS_PATH ANSIBLE_HOME=$ANSIBLE_HOME ansible-playbook -i $COLLECTION_PATH/hosts.yml $COLLECTION_PATH/playbooks/$playbook"
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
    show_deployment_menu
    read -p "Select an option [1-8]: " choice

    case $choice in
        1)
            print_status "Starting full deployment..."
            run_playbook "site.yml"
            ;;
        2)
            print_status "Starting Docker-only deployment..."
            run_playbook "site.yml" "skip_gpu=true"
            ;;
        3)
            print_status "Testing connection to hosts..."
            if ANSIBLE_CONFIG=$ANSIBLE_CONFIG ANSIBLE_COLLECTIONS_PATH=$ANSIBLE_COLLECTIONS_PATH ANSIBLE_HOME=$ANSIBLE_HOME ansible-playbook -i "$COLLECTION_PATH/hosts.yml" "$COLLECTION_PATH/playbooks/test_connection.yml"; then
                print_success "Connection test completed successfully."
            else
                print_error "Connection test failed. Please check your inventory and playbook."
                exit 1
            fi
            ;;
        4)
            print_status "Getting nodes information..."
            if ANSIBLE_CONFIG=$ANSIBLE_CONFIG ANSIBLE_COLLECTIONS_PATH=$ANSIBLE_COLLECTIONS_PATH ANSIBLE_HOME=$ANSIBLE_HOME ansible-playbook -i "$COLLECTION_PATH/hosts.yml" "$COLLECTION_PATH/playbooks/get_node_info.yml"; then
                print_success "Node information retrieved successfully."
            else
                print_error "Failed to retrieve node information."
                exit 1
            fi
            ;;
        5)
            print_status "Getting node addresses..."
            parse_node_info "true"
            ;;
        6)
            print_status "Saving node addresses to CSV..."
            save_node_info_csv
            ;;
        7)
            print_status "Viewing current configuration..."
            view_configuration
            ;;
        8)
            print_success "Exiting deployment script."
            exit 0
            ;;
        *)
            print_error "Invalid option. Please try again."
            ;;
    esac
done 