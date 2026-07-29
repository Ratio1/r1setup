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

# Run user-scoped tooling as the invoking user even when this prerequisite
# installer is run with sudo. Keep the user's local bin directory available so
# a standalone uv installation is found consistently.
REAL_USER_PATH="$REAL_HOME/.local/bin:$PATH"
run_as_real_user() {
    if [ -n "$SUDO_USER" ]; then
        sudo -u "$REAL_USER" env HOME="$REAL_HOME" PATH="$REAL_USER_PATH" "$@"
    else
        env HOME="$REAL_HOME" PATH="$REAL_USER_PATH" "$@"
    fi
}

# Select the Python package manager before Python bootstrap can introduce pip.
# Prefer uv whenever it is usable for the real user.
PYTHON_PACKAGE_MANAGER=""
UV_BIN=""
if run_as_real_user uv --version > /dev/null 2>&1; then
    PYTHON_PACKAGE_MANAGER="uv"
    UV_BIN="$(run_as_real_user sh -c 'command -v uv')"
elif python3 -m pip --version > /dev/null 2>&1; then
    PYTHON_PACKAGE_MANAGER="pip"
else
    PYTHON_PACKAGE_MANAGER="uv (installed)"
    print_message "Installing uv for $REAL_USER..." "$YELLOW"

    UV_INSTALL_SCRIPT="$(run_as_real_user mktemp)"
    if ! run_as_real_user curl -LsSf https://astral.sh/uv/install.sh -o "$UV_INSTALL_SCRIPT"; then
        run_as_real_user rm -f "$UV_INSTALL_SCRIPT"
        print_message "Failed to download the uv installer. Install uv and rerun this script." "$RED"
        exit 1
    fi

    if ! run_as_real_user env UV_INSTALL_DIR="$REAL_HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$UV_INSTALL_SCRIPT"; then
        run_as_real_user rm -f "$UV_INSTALL_SCRIPT"
        print_message "Failed to install uv for $REAL_USER. Install uv and rerun this script." "$RED"
        exit 1
    fi
    run_as_real_user rm -f "$UV_INSTALL_SCRIPT"

    UV_BIN="$REAL_HOME/.local/bin/uv"
    if ! run_as_real_user "$UV_BIN" --version > /dev/null 2>&1; then
        print_message "uv installation did not produce a usable binary at $UV_BIN." "$RED"
        exit 1
    fi
fi

print_message "Selected Python package manager: $PYTHON_PACKAGE_MANAGER" "$GREEN"

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
            $INSTALL_CMD python3 python3-venv
        elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
            $INSTALL_CMD python3 python3-virtualenv
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
PYTHON3_BIN="$(command -v python3)"

# Install SSH client tooling needed by SSH key management
if ! command -v ssh &> /dev/null || ! command -v ssh-keygen &> /dev/null; then
    print_message "Installing OpenSSH client tooling..." "$YELLOW"
    if [[ "$OS_TYPE" == "linux" ]]; then
        if [[ "$OS_NAME" =~ "Ubuntu"|"Debian" ]]; then
            $INSTALL_CMD openssh-client
        elif [[ "$OS_NAME" =~ "CentOS"|"Red Hat"|"Fedora" ]]; then
            $INSTALL_CMD openssh-clients
        fi
    else
        sudo -u "$REAL_USER" $INSTALL_CMD openssh
    fi
fi

# Install OpenSSL for SSH key workflow validation
if ! command -v openssl &> /dev/null; then
    print_message "Installing OpenSSL..." "$YELLOW"
    if [[ "$OS_TYPE" == "linux" ]]; then
        $INSTALL_CMD openssl
    else
        sudo -u "$REAL_USER" $INSTALL_CMD openssl
    fi
fi

# Verify SSH tooling
if ! verify_command ssh || ! verify_command ssh-keygen || ! verify_command openssl; then
    print_message "SSH tooling installation failed" "$RED"
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
VENV_PATH_IN_SETUP_DIR=".r1_venv"

# Define Python executable from the venv
PYTHON_IN_VENV="./$VENV_PATH_IN_SETUP_DIR/bin/python3"

# A prior pip-created environment may be root-owned because older installer
# versions created it before switching back to the real user.
if [ -n "$SUDO_USER" ] && [ -d "./$VENV_PATH_IN_SETUP_DIR" ]; then
    print_message "Setting ownership of ./$VENV_PATH_IN_SETUP_DIR to $REAL_USER..." "$YELLOW"
    if ! chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "./$VENV_PATH_IN_SETUP_DIR"; then
        print_message "Failed to set ownership for ./$VENV_PATH_IN_SETUP_DIR. Please check permissions." "$RED"
    fi
fi

print_message "Creating Python virtual environment at ./$VENV_PATH_IN_SETUP_DIR..." "$YELLOW"
if [[ "$PYTHON_PACKAGE_MANAGER" == uv* ]]; then
    if ! run_as_real_user "$UV_BIN" venv --allow-existing --python "$PYTHON3_BIN" "./$VENV_PATH_IN_SETUP_DIR"; then
        print_message "Failed to create virtual environment at ./$VENV_PATH_IN_SETUP_DIR with uv." "$RED"
        exit 1
    fi
else
    if ! python3 -m venv "./$VENV_PATH_IN_SETUP_DIR"; then
        print_message "Failed to create virtual environment at ./$VENV_PATH_IN_SETUP_DIR." "$RED"
        exit 1
    fi
    if [ -n "$SUDO_USER" ]; then
        print_message "Setting ownership of ./$VENV_PATH_IN_SETUP_DIR to $REAL_USER..." "$YELLOW"
        if ! chown -R "$REAL_USER:$(id -gn "$REAL_USER")" "./$VENV_PATH_IN_SETUP_DIR"; then
            print_message "Failed to set ownership for ./$VENV_PATH_IN_SETUP_DIR. Please check permissions." "$RED"
        fi
    fi
fi

print_message "Installing Python packages into virtual environment (./$VENV_PATH_IN_SETUP_DIR)..." "$YELLOW"
if [[ "$PYTHON_PACKAGE_MANAGER" == uv* ]]; then
    if ! run_as_real_user "$UV_BIN" pip install --python "$PYTHON_IN_VENV" pyyaml typing_extensions certifi; then
        print_message "Failed to install required Python packages (pyyaml, typing_extensions, certifi) with uv." "$RED"
        exit 1
    fi
else
    if ! run_as_real_user "$PYTHON_IN_VENV" -m pip install --upgrade pip || \
       ! run_as_real_user "$PYTHON_IN_VENV" -m pip install pyyaml typing_extensions certifi; then
        print_message "Failed to install required Python packages (pyyaml, typing_extensions, certifi) into the virtual environment." "$RED"
        exit 1
    fi
fi

# Verify core packages installed in venv
if ! run_as_real_user "$PYTHON_IN_VENV" -c 'import certifi; import typing_extensions; import yaml' > /dev/null 2>&1; then
   print_message "Failed to import required Python packages (pyyaml, typing_extensions, certifi) from the virtual environment." "$RED"
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
