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
        INSTALL_DIR="$REAL_HOME/multi-node-launcher"
    else
        INSTALL_DIR="/opt/multi-node-launcher"
    fi
    
    # Set Ansible paths based on OS
    if [[ "$OS_TYPE" == "macos" ]]; then
        ANSIBLE_DIR="$REAL_HOME/.ansible"
    else
        ANSIBLE_DIR="$REAL_HOME/.ansible"
    fi
    
    COLLECTION_PATH="$ANSIBLE_DIR/collections/ansible_collections/ratio1/multi_node_launcher"
}

# Create required directories
create_dirs() {
    # Create working directory if it doesn't exist
    mkdir -p "$INSTALL_DIR"
    
    if [[ "$OS_TYPE" == "linux" ]]; then
        chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$INSTALL_DIR"
    fi
    
    # Create Ansible directory structure
    mkdir -p "$ANSIBLE_DIR/collections"
    if [[ "$OS_TYPE" == "linux" ]]; then
        chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$ANSIBLE_DIR"
    fi
    
    cd "$INSTALL_DIR"
}

# Install Ansible collection
install_collection() {
    print_message "Installing Multi Node Launcher collection..." "$YELLOW"
    
    # Install the collection
    sudo -u "$REAL_USER" env HOME="$REAL_HOME" ansible-galaxy collection install ratio1.multi_node_launcher --force
    
    # Verify collection installation
    COLLECTION_INFO=$(sudo -u "$REAL_USER" env HOME="$REAL_HOME" ansible-galaxy collection list 2>/dev/null | grep "ratio1.multi_node_launcher" || true)
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
create_factory() {
    # Create factory directory
    mkdir -p "$INSTALL_DIR/factory"
    cd "$INSTALL_DIR/factory"
    
    # Create template files
    cat > hosts.yml << 'EOF'
---
all:
  children:
    gpu_nodes:
      hosts:
        # Add your GPU nodes here
        # Example:
        # gpu-node-1:
        #   ansible_host: 192.168.1.100
        #   ansible_user: ubuntu
        #   ansible_ssh_private_key_file: ~/.ssh/id_rsa
EOF
    
    cat > ansible.cfg << 'EOF'
[defaults]
inventory = hosts.yml
host_key_checking = False
stdout_callback = yaml
EOF
    
    cat > deploy.yml << 'EOF'
---
- name: Deploy Multi Node Environment
  hosts: gpu_nodes
  become: true
  gather_facts: true
  tasks:
    - name: Include prerequisites role
      include_role:
        name: ratio1.multi_node_launcher.prerequisites

    - name: Include NVIDIA GPU role
      include_role:
        name: ratio1.multi_node_launcher.nvidia_gpu
      when: not skip_gpu | default(false)

    - name: Include Docker role
      include_role:
        name: ratio1.multi_node_launcher.docker
EOF
    
    cat > deploy-gpu.yml << 'EOF'
---
- name: Deploy GPU Environment
  hosts: gpu_nodes
  become: true
  gather_facts: true
  tasks:
    - name: Include NVIDIA GPU role
      include_role:
        name: ratio1.multi_node_launcher.nvidia_gpu
EOF
    
    cat > deploy-config.yml << 'EOF'
---
- name: Test Connection and Configuration
  hosts: gpu_nodes
  gather_facts: true
  tasks:
    - name: Ping hosts
      ping:

    - name: Get OS information
      command: cat /etc/os-release
      register: os_info

    - name: Display OS information
      debug:
        var: os_info.stdout_lines
EOF
    
    # Set proper permissions
    chmod 600 hosts.yml
    chmod 644 ansible.cfg deploy.yml deploy-gpu.yml deploy-config.yml
}

# Set up Python environment
setup_python_env() {
    # Create a virtual environment for Python
    VENV_DIR="$INSTALL_DIR/venv"
    
    # Skip if venv already exists
    if [ ! -d "$VENV_DIR" ]; then
        if [[ "$OS_TYPE" == "linux" ]]; then
            python3 -m venv "$VENV_DIR"
            chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$VENV_DIR"
        else
            sudo -u "$REAL_USER" python3 -m venv "$VENV_DIR"
        fi
    
        # Verify virtual environment creation
        if [ ! -f "$VENV_DIR/bin/activate" ]; then
            print_message "Failed to create virtual environment" "$RED"
            exit 1
        fi
    
        # Install Python requirements in the virtual environment
        sudo -u "$REAL_USER" bash << EOF
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install pyyaml typing_extensions
EOF
    fi
    
    # Create activation script
    cat > "$INSTALL_DIR/activate_env.sh" << EOF
#!/bin/bash
source "$VENV_DIR/bin/activate"
export PATH="$INSTALL_DIR/factory:\$PATH"
export ANSIBLE_CONFIG="$INSTALL_DIR/factory/ansible.cfg"
EOF
    
    chmod +x "$INSTALL_DIR/activate_env.sh"
}

# Set ownership and permissions
set_ownership() {
    # Set proper ownership for all files
    if [[ "$OS_TYPE" == "linux" ]]; then
        chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$INSTALL_DIR"
    else
        chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$INSTALL_DIR"
    fi
    
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
    
    BASHRC_ENTRY="source $INSTALL_DIR/activate_env.sh"
    if ! grep -q "$BASHRC_ENTRY" "$SHELL_RC_PATH"; then
        echo "$BASHRC_ENTRY" >> "$SHELL_RC_PATH"
    fi
}

# Verify the setup
verify_setup() {
    print_message "\nVerifying installation..." "$YELLOW"
    
    # Check if all required files exist
    required_files=(
        "$INSTALL_DIR/factory/hosts.yml"
        "$INSTALL_DIR/factory/ansible.cfg"
        "$INSTALL_DIR/factory/deploy.yml"
        "$INSTALL_DIR/factory/deploy-gpu.yml"
        "$INSTALL_DIR/factory/deploy-config.yml"
        "$INSTALL_DIR/activate_env.sh"
        "$INSTALL_DIR/venv/bin/activate"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_message "Error: Missing required file: $file" "$RED"
            exit 1
        fi
    done
    
    print_message "All required files are present" "$GREEN"
    
    # Verify Python packages in virtual environment as the real user
    sudo -u "$REAL_USER" bash << EOF
source "$INSTALL_DIR/venv/bin/activate"
if ! python3 -c "import yaml, typing_extensions" 2>/dev/null; then
    echo -e "${RED}Error: Required Python packages are not installed properly${NC}"
    exit 1
fi
EOF
    
    print_message "Python packages verified" "$GREEN"
}

# Print next steps
print_next_steps() {
    print_message "\nInstallation completed successfully!" "$GREEN"
    print_message "\nNext steps:" "$YELLOW"
    print_message "1. Run the configuration script:" "$NC"
    print_message "   source $INSTALL_DIR/activate_env.sh" "$NC"
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
    create_factory
    setup_python_env
    set_ownership
    verify_setup
    print_next_steps
    
    # Activate the environment for immediate use for the real user
    sudo -u "$REAL_USER" bash -c "source $INSTALL_DIR/activate_env.sh"
}

# Run the main function
main