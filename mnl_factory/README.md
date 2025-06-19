# Multi-Node Launcher

Multi-Node Launcher is a solution for easily setting up and managing GPU nodes using Ansible. This guide provides step-by-step instructions to quickly configure your system and manage your GPU nodes.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Setup](#quick-setup)
- [Initial Setup](#initial-setup)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Notes](#notes)

## Overview

Multi-Node Launcher automates the setup process for GPU nodes with Ansible. It ensures that required dependencies are installed and configuration is performed in a reliable, idempotent manner.

## Prerequisites

Before you start, ensure that you have met the following requirements:

1. Ansible installed on your control node
2. SSH access to target nodes
3. Sudo privileges on target nodes
4. NVIDIA GPU(s) on target nodes
5. Internet access for package downloads

## Quick Setup

You can quickly set up your GPU nodes by running the following one-liner:

```bash
curl -sL https://raw.githubusercontent.com/Ratio1/r1setup/refs/heads/main/install.sh -o install-factory.sh && bash install-factory.sh
```

This command will:
- Create a temporary setup directory
- Download necessary scripts
- Execute prerequisite checks
- Perform Ansible setup and configuration

## Initial Setup

Before running the playbook, follow these steps:

1. Install required Ansible collections:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```
2. Configure your hosts by editing the `inventory/hosts.yml` file.

## Usage

1. Test connectivity to your nodes:
   ```bash
   ansible all -i inventory/hosts.yml -m ping
   ```
2. Execute the playbook:
   ```bash
   ansible-playbook -i inventory/hosts.yml playbooks/site.yml
   ```

## Troubleshooting

If you encounter issues during setup or execution, consider the following:

- Verify that all prerequisites are met.
- Ensure that SSH keys and permissions are correctly configured.
- Consult the Ansible logs for detailed error messages.
- Search for known issues on the project's GitHub repository or open a new issue.

## Notes

- The playbook is idempotent and can be run multiple times safely.
- Ensure adequate cooling and power for GPU operations.
- For macOS users: This setup uses Homebrew for package management. Ensure Homebrew is installed prior to running the setup.
