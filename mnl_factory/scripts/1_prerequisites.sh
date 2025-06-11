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

# Ensure python3-venv is installed (especially for Debian/Ubuntu)
if [[ "$OS_TYPE" == "linux" ]]; then
    if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
        print_message "Ensuring python3-venv is installed..." "$YELLOW"
        $INSTALL_CMD python3-venv
    fi
fi

# Define Venv Path (relative to $SETUP_DIR where this script runs)
VENV_PATH_IN_SETUP_DIR="mnl_venv"

print_message "Creating Python virtual environment at ./$VENV_PATH_IN_SETUP_DIR..." "$YELLOW"
python3 -m venv "./$VENV_PATH_IN_SETUP_DIR"
if [ $? -ne 0 ]; then
    print_message "Failed to create virtual environment at ./$VENV_PATH_IN_SETUP_DIR." "$RED"
    exit 1
fi

# Ensure the venv directory is owned by the original user if sudo was used
# $REAL_USER is defined at the beginning of this script
if [ -n "$SUDO_USER" ]; then
    print_message "Setting ownership of ./$VENV_PATH_IN_SETUP_DIR to $REAL_USER..." "$YELLOW"
    chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "./$VENV_PATH_IN_SETUP_DIR"
    if [ $? -ne 0 ]; then
        print_message "Failed to set ownership for ./$VENV_PATH_IN_SETUP_DIR. Please check permissions." "$RED"
        # It might be non-fatal if REAL_USER already owns it (e.g. if script not run with sudo, though it usually is)
    fi
fi

# Define Python and Pip executables from the venv
PYTHON_IN_VENV="./$VENV_PATH_IN_SETUP_DIR/bin/python3"
PIP_IN_VENV="./$VENV_PATH_IN_SETUP_DIR/bin/pip"

# Upgrade pip and install required packages into the venv
print_message "Installing Python packages into virtual environment (./$VENV_PATH_IN_SETUP_DIR)..." "$YELLOW"

# Pip commands should run as $REAL_USER if sudo was used for 1_prerequisites.sh,
# to ensure packages are installed correctly within the user-owned venv.
if [ -n "$SUDO_USER" ]; then
    sudo -u "$REAL_USER" HOME="$REAL_HOME" "$PIP_IN_VENV" install --upgrade pip
    sudo -u "$REAL_USER" HOME="$REAL_HOME" "$PIP_IN_VENV" install pyyaml typing_extensions
else
    # If script somehow runs without sudo (not the typical path for this script)
    "$PIP_IN_VENV" install --upgrade pip
    "$PIP_IN_VENV" install pyyaml typing_extensions
fi

# Verify core packages installed in venv
if ! sudo -u "$REAL_USER" HOME="$REAL_HOME" "$PYTHON_IN_VENV" -m pip show pyyaml > /dev/null 2>&1 || \
   ! sudo -u "$REAL_USER" HOME="$REAL_HOME" "$PYTHON_IN_VENV" -m pip show typing_extensions > /dev/null 2>&1; then
   if [ -n "$SUDO_USER" ]; then
        print_message "Failed to install required Python packages (pyyaml, typing_extensions) into the virtual environment as $REAL_USER." "$RED"
   else
        print_message "Failed to install required Python packages (pyyaml, typing_extensions) into the virtual environment." "$RED"
   fi
   exit 1
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

print_message "\nPrerequisites installed successfully!" "$GREEN"
