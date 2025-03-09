#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

# Check for bash
if ! command -v bash >/dev/null 2>&1; then
    print_message "Bash is required for this script. Please install bash first." "$RED"
    exit 1
fi

# Get the actual user when running with sudo
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
OS_TYPE=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
    print_message "Detected macOS system" "$GREEN"
elif [[ "$OSTYPE" == "linux"* ]]; then
    OS_TYPE="linux"
    print_message "Detected Linux system" "$GREEN"
else
    print_message "Unsupported OS: $OSTYPE" "$RED"
    exit 1
fi

# Working directly in the current directory
print_message "Working in the current directory: $(pwd)" "$YELLOW"

# Download setup scripts
print_message "Downloading setup scripts..." "$YELLOW"
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_ansible_setup.sh
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_configure.py
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/4_run_setup.sh

# Make scripts executable
chmod +x 1_prerequisites.sh 2_ansible_setup.sh 3_configure.py 4_run_setup.sh

# Fix ownership of all files if running as root
if [ "$(id -u)" -eq 0 ] && [ -n "$SUDO_USER" ]; then
    chown "$REAL_USER" 1_prerequisites.sh 2_ansible_setup.sh 3_configure.py 4_run_setup.sh
fi

# Fix line endings (in case of CRLF issues)
if command -v dos2unix >/dev/null 2>&1; then
    print_message "Converting line endings..." "$YELLOW"
    dos2unix 1_prerequisites.sh 2_ansible_setup.sh 4_run_setup.sh
else
    if [ "$OS_TYPE" = "macos" ]; then
        print_message "dos2unix not found, attempting to fix line endings with sed..." "$YELLOW"
        for script in 1_prerequisites.sh 2_ansible_setup.sh 4_run_setup.sh; do
            sed -i '' 's/\r$//' "$script"
        done
    elif [ "$OS_TYPE" = "linux" ]; then
        print_message "dos2unix not found, attempting to fix line endings with sed..." "$YELLOW"
        for script in 1_prerequisites.sh 2_ansible_setup.sh 4_run_setup.sh; do
            sed -i 's/\r$//' "$script"
        done
    fi
fi

# Remove quarantine attribute on macOS
if [ "$OS_TYPE" = "macos" ]; then
    print_message "Removing quarantine attributes..." "$YELLOW"
    xattr -d com.apple.quarantine 1_prerequisites.sh 2>/dev/null
    xattr -d com.apple.quarantine 2_ansible_setup.sh 2>/dev/null
    xattr -d com.apple.quarantine 3_configure.py 2>/dev/null
    xattr -d com.apple.quarantine 4_run_setup.sh 2>/dev/null
fi

# Ensure bash shebang is correct
print_message "Ensuring correct bash path in scripts..." "$YELLOW"
for script in 1_prerequisites.sh 2_ansible_setup.sh 4_run_setup.sh; do
    # Get first line of the script
    first_line=$(head -n 1 "$script")
    # Check if it's a shebang
    if [[ $first_line == \#\!* ]]; then
        # Replace with correct bash path
        sed -i.bak "1s|.*|#!/bin/bash|" "$script"
        rm -f "${script}.bak"
    fi
done

print_message "\nSetup process:" "$GREEN"

# On macOS, don't use sudo for Homebrew or pip installations
if [ "$OS_TYPE" = "macos" ]; then
    print_message "1. Installing prerequisites for macOS..." "$YELLOW"
    # If running as root, run this as the real user
    if [ "$(id -u)" -eq 0 ]; then
        print_message "Running homebrew and pip installations as real user: $REAL_USER" "$YELLOW"
        # Modify the prerequisites script to avoid sudo usage
        sed -i.bak 's/sudo pip3/pip3/g' 1_prerequisites.sh
        
        # Run the command directly without using su
        print_message "Setting up prerequisites..." "$YELLOW"
        sudo -u "$REAL_USER" bash ./1_prerequisites.sh
    else
        bash ./1_prerequisites.sh
    fi
else
    print_message "1. Installing prerequisites for Linux..." "$YELLOW"
    sudo bash ./1_prerequisites.sh
fi

print_message "2. Ansible setup..." "$YELLOW"
# Run ansible setup as real user on macOS
if [ "$OS_TYPE" = "macos" ] && [ "$(id -u)" -eq 0 ]; then
    # Add REAL_USER and REAL_HOME variables to the script
    echo "REAL_USER='$REAL_USER'" > ansible_setup_env.sh
    echo "REAL_HOME='$REAL_HOME'" >> ansible_setup_env.sh
    cat 2_ansible_setup.sh >> ansible_setup_env.sh
    chmod +x ansible_setup_env.sh
    chown "$REAL_USER" ansible_setup_env.sh
    
    # Run as the real user using sudo -u
    sudo -u "$REAL_USER" bash ./ansible_setup_env.sh
else
    bash ./2_ansible_setup.sh
fi

print_message "\n3. Configuring nodes..." "$YELLOW"
# Run python script as real user on macOS
if [ "$OS_TYPE" = "macos" ] && [ "$(id -u)" -eq 0 ]; then
    sudo -u "$REAL_USER" python3 ./3_configure.py
else
    python3 ./3_configure.py
fi

print_message "\n4. Running setup..." "$YELLOW"
# Run setup script as real user on macOS
if [ "$OS_TYPE" = "macos" ] && [ "$(id -u)" -eq 0 ]; then
    sudo -u "$REAL_USER" bash ./4_run_setup.sh
else
    bash ./4_run_setup.sh
fi

print_message "\nScript execution completed successfully!" "$GREEN"
print_message "You may want to remove the setup scripts with: rm -f {1,2,3,4}_*.{sh,py} ansible_setup_env.sh" "$YELLOW"
