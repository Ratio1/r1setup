# r1setup - Unified Multi-Node Launcher Setup

## Overview
`r1setup` replaces the old individual scripts (3_configure.py, 4_run_setup.sh) with a unified, user-friendly interface.

## Installation
```bash
curl -sSL https://raw.githubusercontent.com/Ratio1/r1setup/refs/heads/main/install.sh | bash
```

## Usage
After installation, run from anywhere:
```bash
r1setup
```

## Features
### Node Management
- Configure GPU nodes (IP, SSH, authentication)
- View current configuration
- Test node connectivity

### Deployment  
- Full deployment (Docker + NVIDIA + GPU)
- Docker-only deployment

### Information
- Get node information
- Display/export node addresses

### Settings
- Change network environment (mainnet/testnet/devnet)

## File Structure
```
~/.ratio1/r1_setup/r1setup    # Main script
/usr/local/bin/r1setup                # System-wide command
```

## Migration
Old script functionality is preserved:
- 3_configure.py → "Configure nodes" menu
- 4_run_setup.sh → "Deploy" options

All existing configurations remain compatible. 