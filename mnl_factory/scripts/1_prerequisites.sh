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
    if [[ "$OSTYPE" == "darwin"* ]]; then
        REAL_HOME=$(dscl . -read /Users/"$SUDO_USER" NFSHomeDirectory | awk '{print $2}')
    else
        REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    fi
else
    REAL_USER=$USER
    REAL_HOME=$HOME
fi

# Detect OS
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

# Check if running with sudo (only required for Linux)
if [[ "$OS_TYPE" == "linux" && "$EUID" -ne 0 ]]; then
    print_message "Please run with sudo on Linux" "$RED"
    exit 1
fi

# Set package manager commands based on OS
if [[ "$OS_TYPE" == "macos" ]]; then
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        print_message "Homebrew is not installed. Please install Homebrew first:" "$RED"
        print_message "/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"" "$YELLOW"
        exit 1
    fi
    
    # Set macOS installation commands
    INSTALL_CMD="brew install"
    UPDATE_CMD="brew update"
    REPO_CMD="brew tap"
    
elif [[ "$OS_TYPE" == "linux" ]]; then
    # Set Linux installation commands based on distribution
    if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
        INSTALL_CMD="apt-get install -y"
        UPDATE_CMD="apt-get update"
        REPO_CMD="apt-add-repository --yes --update"
    elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
        INSTALL_CMD="dnf install -y"
        UPDATE_CMD="dnf check-update"
        REPO_CMD="dnf config-manager --add-repo"
    else
        print_message "Unsupported Linux distribution: $OS_NAME" "$RED"
        exit 1
    fi
fi

# Install directory
INSTALL_DIR="/opt/multi-node-launcher"
if [[ "$OS_TYPE" == "macos" ]]; then
    # On macOS, use a user-accessible directory instead of /opt
    INSTALL_DIR="$REAL_HOME/multi-node-launcher"
fi

# Create install directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Update package repositories
print_message "Updating package repositories..." "$YELLOW"
if [[ "$OS_TYPE" == "linux" ]]; then
    eval $UPDATE_CMD
else
    sudo -u "$REAL_USER" $UPDATE_CMD
fi

# Install Python if not present
if ! command -v python3 &> /dev/null; then
    print_message "Installing Python..." "$YELLOW"
    if [[ "$OS_TYPE" == "linux" ]]; then
        if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
            $INSTALL_CMD python3 python3-pip python3-venv
        elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
            $INSTALL_CMD python3 python3-pip python3-virtualenv
        fi
    else
        sudo -u "$REAL_USER" $INSTALL_CMD python
    fi
fi

# Verify Python installation
if ! verify_command python3; then
    print_message "Python installation failed" "$RED"
    exit 1
fi

# Upgrade pip and install required packages
print_message "Installing Python packages..." "$YELLOW"
if [[ "$OS_TYPE" == "linux" ]]; then
    python3 -m pip install --upgrade pip
    python3 -m pip install pyyaml typing_extensions
else
    sudo -u "$REAL_USER" python3 -m pip install --upgrade pip
    sudo -u "$REAL_USER" python3 -m pip install pyyaml typing_extensions
fi

# Install Ansible if not present
if ! command -v ansible &> /dev/null; then
    print_message "Installing Ansible..." "$YELLOW"
    if [[ "$OS_TYPE" == "linux" ]]; then
        if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
            $INSTALL_CMD software-properties-common
            $REPO_CMD ppa:ansible/ansible
            $INSTALL_CMD ansible
        elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
            $INSTALL_CMD ansible
        fi
    else
        sudo -u "$REAL_USER" $INSTALL_CMD ansible
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
    if [[ "$OS_TYPE" == "linux" ]]; then
        if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
            $INSTALL_CMD sshpass
        elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
            $INSTALL_CMD sshpass
        fi
    else
        sudo -u "$REAL_USER" $INSTALL_CMD sshpass
    fi
fi

# Verify sshpass installation
if ! verify_command sshpass; then
    print_message "sshpass installation failed" "$RED"
    exit 1
fi

# Create a virtual environment for Python
VENV_DIR="$INSTALL_DIR/venv"
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
if [[ "$OS_TYPE" == "linux" ]]; then
    sudo -u "$REAL_USER" bash << EOF
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install pyyaml typing_extensions
EOF
else
    sudo -u "$REAL_USER" bash << EOF
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install pyyaml typing_extensions
EOF
fi

# Create activation script with OS-specific paths
cat > "$INSTALL_DIR/activate_env.sh" << EOF
#!/bin/bash
source "$VENV_DIR/bin/activate"
export PATH="$INSTALL_DIR/factory:\$PATH"
export ANSIBLE_CONFIG="$INSTALL_DIR/factory/ansible.cfg"
EOF

chmod +x "$INSTALL_DIR/activate_env.sh"

# Set proper ownership for all files
if [[ "$OS_TYPE" == "linux" ]]; then
    chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$INSTALL_DIR"
else
    chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "$INSTALL_DIR"
fi

print_message "\nPrerequisites installed successfully!" "$GREEN"

# Activate the environment for immediate use for the real user
sudo -u "$REAL_USER" bash -c "source $INSTALL_DIR/activate_env.sh"