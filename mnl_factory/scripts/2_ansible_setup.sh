#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

# Get the actual user's home directory and username
if [ -n "$SUDO_USER" ]; then
    REAL_USER=$SUDO_USER
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_USER=$USER
    REAL_HOME=$HOME
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
elif type "sw_vers" &> /dev/null; then
    OS_NAME="macOS"
else
    print_message "Unsupported OS" "$RED"
    exit 1
fi

# Check if OS is supported
SUPPORTED_OS=("Ubuntu" "Debian" "CentOS" "Red Hat Enterprise Linux" "Fedora")
if [[ ! " ${SUPPORTED_OS[@]} " =~ " ${OS_NAME} " ]]; then
    print_message "This script only supports ${SUPPORTED_OS[*]}" "$RED"
    exit 1
fi

# Create working directory
INSTALL_DIR="/opt/multi-node-launcher"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Install Ansible collection for the real user
print_message "Installing Multi Node Launcher collection..." "$YELLOW"
sudo -u "$REAL_USER" ansible-galaxy collection install ratio1.multi_node_launcher --force

# Verify collection installation with improved path detection
COLLECTION_PATH=$(sudo -u "$REAL_USER" bash -c 'ansible-galaxy collection list 2>/dev/null | grep "ratio1.multi_node_launcher" || true')
if [ -z "$COLLECTION_PATH" ]; then
    print_message "Failed to detect installed collection" "$RED"
    exit 1
fi

# Extract version and path from collection info
COLLECTION_VER=$(echo "$COLLECTION_PATH" | awk '{print $2}')
COLLECTION_INSTALL_PATH="$REAL_HOME/.ansible/collections/ansible_collections/ratio1/multi_node_launcher"

if [ ! -d "$COLLECTION_INSTALL_PATH" ]; then
    print_message "Collection directory not found at: $COLLECTION_INSTALL_PATH" "$RED"
    exit 1
fi

print_message "Collection ratio1.multi_node_launcher v$COLLECTION_VER installed successfully" "$GREEN"
print_message "Collection path: $COLLECTION_INSTALL_PATH" "$GREEN"

# Create factory directory
mkdir -p factory
cd factory

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

# Create a virtual environment for Python
VENV_DIR="$INSTALL_DIR/venv"
python3 -m venv "$VENV_DIR"
chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$VENV_DIR"

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

# Create activation script
cat > "$INSTALL_DIR/activate_env.sh" << 'EOF'
#!/bin/bash
source "/opt/multi-node-launcher/venv/bin/activate"
export PATH="/opt/multi-node-launcher/factory:$PATH"
export ANSIBLE_CONFIG="/opt/multi-node-launcher/factory/ansible.cfg"
EOF

chmod +x "$INSTALL_DIR/activate_env.sh"

# Set proper ownership for all files
chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$INSTALL_DIR"

# Add environment setup to the real user's .bashrc if not already present
BASHRC_PATH="$REAL_HOME/.bashrc"
BASHRC_ENTRY="source /opt/multi-node-launcher/activate_env.sh"
if ! grep -q "$BASHRC_ENTRY" "$BASHRC_PATH"; then
    echo "$BASHRC_ENTRY" >> "$BASHRC_PATH"
fi

# Verify final setup
print_message "\nVerifying installation..." "$YELLOW"

# Check if all required files exist
required_files=(
    "$INSTALL_DIR/factory/hosts.yml"
    "$INSTALL_DIR/factory/ansible.cfg"
    "$INSTALL_DIR/factory/deploy.yml"
    "$INSTALL_DIR/factory/deploy-gpu.yml"
    "$INSTALL_DIR/factory/deploy-config.yml"
    "$INSTALL_DIR/activate_env.sh"
    "$VENV_DIR/bin/activate"
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
source "$VENV_DIR/bin/activate"
if ! python3 -c "import yaml, typing_extensions" 2>/dev/null; then
    echo -e "${RED}Error: Required Python packages are not installed properly${NC}"
    exit 1
fi
EOF

print_message "Python packages verified" "$GREEN"

print_message "\nInstallation completed successfully!" "$GREEN"
print_message "\nNext steps:" "$YELLOW"
print_message "1. Run the configuration script:" "$NC"
print_message "   source /opt/multi-node-launcher/activate_env.sh" "$NC"
print_message "   python3 /opt/multi-node-launcher/factory/configure.py" "$NC"
print_message "2. After configuration, deploy with:" "$NC"
print_message "   ansible-playbook deploy.yml" "$NC"

# Activate the environment for immediate use for the real user
sudo -u "$REAL_USER" bash -c "source $INSTALL_DIR/activate_env.sh"