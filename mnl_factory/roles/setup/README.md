# Setup Role

This role orchestrates the complete setup of GPU nodes by coordinating the execution of other roles and performing final configuration tasks.

## Quick Start

Copy and run this script to set up your GPU nodes:

```bash
#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_message() {
    echo -e "${2}${1}${NC}"
}

# Create temporary directory
TEMP_DIR=$(mkdir mnl_setup)
cd "$TEMP_DIR"

# Download setup scripts
print_message "Downloading setup scripts..." "$YELLOW"
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/1_prerequisites.sh
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/2_configure.py
curl -O https://raw.githubusercontent.com/Ratio1/multi-node-launcher/refs/heads/main/mnl_factory/scripts/3_run_setup.sh

# Make scripts executable
chmod +x 1_prerequisites.sh 2_configure.py 3_run_setup.sh

print_message "\nSetup process:" "$GREEN"
print_message "1. Installing prerequisites..." "$YELLOW"
sudo ./1_prerequisites.sh

print_message "\n2. Configuring nodes..." "$YELLOW"
python3 2_configure.py

print_message "\n3. Running setup..." "$YELLOW"
sudo ./3_run_setup.sh
```

Save this script as `setup.sh`, make it executable with `chmod +x setup.sh`, and run it with `sudo ./setup.sh`.

## What the Setup Does

1. **Prerequisites** (`1_prerequisites.sh`):
   - Installs required packages (Python, Ansible, sshpass)
   - Sets up virtual environment
   - Installs Ansible collection

2. **Configuration** (`2_configure.py`):
   - Interactive node configuration
   - SSH authentication setup
   - Configuration validation

3. **Deployment** (`3_run_setup.sh`):
   - Full deployment (Docker + NVIDIA drivers + GPU setup)
   - Docker-only deployment option
   - Connection testing
   - Node information retrieval
   - Configuration management

## Requirements

- Ubuntu-based system
- Internet connection
- Sudo privileges

## Available Options

After setup, you can use the following options through the deployment menu:

1. Full deployment (Docker + NVIDIA drivers + GPU setup)
2. Docker-only deployment
3. Test connection to hosts
4. Get nodes information
5. View current configuration
6. Exit

## License

MIT

## Author Information

- Andrei Damian
- Vitalii Toderian 