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

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR" || exit 1
print_message "Using temporary directory: $TEMP_DIR" "$YELLOW"

# Download setup scripts
print_message "Downloading setup scripts..." "$YELLOW"
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_ansible_setup.sh
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_configure.py
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/4_run_setup.sh

# Make scripts executable
chmod +x 1_prerequisites.sh 2_ansible_setup.sh 3_configure.py 4_run_setup.sh

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

print_message "\nSetup process:" "$GREEN"
print_message "1. Installing prerequisites..." "$YELLOW"
sudo sh ./1_prerequisites.sh

print_message "2. Ansible setup..." "$YELLOW"
sh ./2_ansible_setup.sh

print_message "\n3. Configuring nodes..." "$YELLOW"
python3 ./3_configure.py

print_message "\n4. Running setup..." "$YELLOW"
# Run with explicit interpreter to avoid potential shebang issues
sh ./4_run_setup.sh

# Clean up
print_message "\nCleaning up temporary files..." "$YELLOW"
cd - >/dev/null || exit 1
rm -rf "$TEMP_DIR"
print_message "Installation complete!" "$GREEN"
