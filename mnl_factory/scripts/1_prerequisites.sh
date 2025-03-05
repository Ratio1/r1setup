#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

verify_command() {
    if ! command -v "$1" &> /dev/null; then
        print_message "Error: $1 is not installed properly" "$RED"
        return 1
    fi
    return 0
}

# Get the actual user's home directory and username
if [ -n "$SUDO_USER" ]; then
    REAL_USER=$SUDO_USER
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    REAL_USER=$USER
    REAL_HOME=$HOME
fi

# Check if running with sudo
if [ "$EUID" -ne 0 ]; then
    print_message "Please run with sudo" "$RED"
    exit 1
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

# Install Python if not present
if ! command -v python3 &> /dev/null; then
    print_message "Installing Python..." "$YELLOW"
    if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
        apt-get update
        apt-get install -y python3 python3-pip python3-venv
    elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
        dnf install -y python3 python3-pip python3-virtualenv
    fi
fi

# Verify Python installation
if ! verify_command python3; then
    print_message "Python installation failed" "$RED"
    exit 1
fi

# Upgrade pip and install required packages
print_message "Installing Python packages..." "$YELLOW"
python3 -m pip install --upgrade pip
python3 -m pip install pyyaml typing_extensions

# Install Ansible if not present
if ! command -v ansible &> /dev/null; then
    print_message "Installing Ansible..." "$YELLOW"
    if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
        apt-get install -y software-properties-common
        apt-add-repository --yes --update ppa:ansible/ansible
        apt-get install -y ansible
    elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
        dnf install -y ansible
    fi
fi

# Verify Ansible installation
if ! verify_command ansible; then
    print_message "Ansible installation failed" "$RED"
    exit 1
fi

# Install sshpass if not present
if ! command -v sshpass &> /dev/null; then
    print_message "Installing sshpass..." "$YELLOW"
    if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
        apt-get install -y sshpass
    elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
        dnf install -y sshpass
    fi
fi

# Verify sshpass installation
if ! verify_command sshpass; then
    print_message "sshpass installation failed" "$RED"
    exit 1
fi

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

print_message "\nInstallation completed successfully!" "$GREEN"

# Activate the environment for immediate use for the real user
sudo -u "$REAL_USER" bash -c "source $INSTALL_DIR/activate_env.sh"