#!/bin/sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect OS
detect_os() {
    # Use uname instead of OSTYPE which is bash-specific
    OS_NAME=$(uname -s)
    case "$OS_NAME" in
        Darwin*)
            OS_TYPE="macos"
            log "INFO" "Detected macOS system" "$GREEN"
            ;;
        Linux*)
            OS_TYPE="linux"
            log "INFO" "Detected Linux system" "$GREEN"
            ;;
        *)
            log "ERROR" "Unsupported OS: $OS_NAME" "$RED"
            exit 1
            ;;
    esac
}

# Define log levels as numeric constants instead of associative array
DEBUG_LEVEL=0
INFO_LEVEL=1
WARNING_LEVEL=2
ERROR_LEVEL=3

# Default to INFO if not set
LOG_LEVEL=${LOG_LEVEL:-"INFO"}

# Convert LOG_LEVEL to numeric value
get_log_level_value() {
    case "$1" in
        "DEBUG"|"debug") echo $DEBUG_LEVEL ;;
        "INFO"|"info") echo $INFO_LEVEL ;;
        "WARNING"|"warning") echo $WARNING_LEVEL ;;
        "ERROR"|"error") echo $ERROR_LEVEL ;;
        *) echo $INFO_LEVEL ;;  # Default to INFO for unknown values
    esac
}

# Normalize log level to uppercase
normalize_log_level() {
    case "$(echo "$1" | tr '[:lower:]' '[:upper:]')" in
        "DEBUG") echo "DEBUG" ;;
        "INFO") echo "INFO" ;;
        "WARNING") echo "WARNING" ;;
        "ERROR") echo "ERROR" ;;
        *) echo "INFO" ;;  # Default to INFO for unknown values
    esac
}

# Initialize log level
LOG_LEVEL=$(normalize_log_level "$LOG_LEVEL")
LOG_LEVEL_VALUE=$(get_log_level_value "$LOG_LEVEL")

# Logging functions
log() {
    local level=$1
    local message=$2
    local color=$3
    local level_value=$(get_log_level_value "$level")
    
    # Check if we should log this message based on level
    if [ "$level_value" -ge "$LOG_LEVEL_VALUE" ]; then
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
get_user_info() {
    if [ -n "$SUDO_USER" ]; then
        REAL_USER=$SUDO_USER
        if [ "$OS_TYPE" = "macos" ]; then
            REAL_HOME=$(dscl . -read /Users/"$SUDO_USER" NFSHomeDirectory | awk '{print $2}')
        else
            REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        fi
    else
        REAL_USER=$USER
        REAL_HOME=$HOME
    fi

    debug "Real user: $REAL_USER"
    debug "Real home: $REAL_HOME"
}

# Set installation directories based on OS
set_install_dirs() {
    if [ "$OS_TYPE" = "macos" ]; then
        INSTALL_DIR="$REAL_HOME/multi-node-launcher"
    else
        INSTALL_DIR="/opt/multi-node-launcher"
    fi
    
    # Set Ansible paths based on OS
    ANSIBLE_DIR="$REAL_HOME/.ansible"
    
    # Collection path will be the same regardless of OS but path may differ
    COLLECTION_PATH="$ANSIBLE_DIR/collections/ansible_collections/ratio1/multi_node_launcher"
    debug "Installation directory: $INSTALL_DIR"
    debug "Ansible directory: $ANSIBLE_DIR"
    debug "Collection path: $COLLECTION_PATH"
}

# Set Ansible environment variables
set_ansible_env() {
    # Set Ansible environment variables to use the real user's home directory
    export ANSIBLE_CONFIG="$ANSIBLE_DIR/ansible.cfg"
    export ANSIBLE_COLLECTIONS_PATH="$ANSIBLE_DIR/collections"
    export ANSIBLE_HOME="$ANSIBLE_DIR"

    debug "Ansible environment variables set"
    debug "ANSIBLE_CONFIG: $ANSIBLE_CONFIG"
    debug "ANSIBLE_COLLECTIONS_PATH: $ANSIBLE_COLLECTIONS_PATH"
    debug "ANSIBLE_HOME: $ANSIBLE_HOME"
}

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
    if ! command -v ansible > /dev/null 2>&1; then
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
    echo "9) Configure nodes - Run the configuration script to add/delete/update node settings."
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

# Main function
main() {
    # Initialize environment
    detect_os
    get_user_info
    set_install_dirs
    set_ansible_env

    info "Multi Node Launcher Deployment"
    info "============================="

#    debug "Checking virtual environment"
#    # Check if we're in the correct environment
#    if [ -z "$VIRTUAL_ENV" ]; then
#        debug "No virtual environment active"
#        VENV_ACTIVATE="$INSTALL_DIR/activate_env.sh"
#        if [ -f "$VENV_ACTIVATE" ]; then
#            info "Activating virtual environment..."
#            debug "Activating from: $VENV_ACTIVATE"
#            . "$VENV_ACTIVATE"
#        else
#            debug "Virtual environment activation script not found at $VENV_ACTIVATE"
#            error "Virtual environment not found!"
#            warning "Please run the prerequisites script first."
#            exit 1
#        fi
#    fi
#
#    debug "Virtual environment active: $VIRTUAL_ENV"

    # Verify ansible installation
    verify_ansible

    # Check hosts configuration
    check_hosts_config

    # Main loop
    while true; do
        show_deployment_menu
        read -p "Select an option [1-9]: " choice

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
            9)
                print_status "Running node configuration script..."
                # Get the path to the script relative to the current script
                CONFIG_SCRIPT_PATH="$(dirname "$0")/3_configure.py"
                
                if [ -f "$CONFIG_SCRIPT_PATH" ]; then
                    python3 "$CONFIG_SCRIPT_PATH"
                else
                    print_error "Configuration script not found at: $CONFIG_SCRIPT_PATH"
                    exit 1
                fi
                ;;
            *)
                print_error "Invalid option. Please try again."
                ;;
        esac
    done
}

# Run the main function
main 