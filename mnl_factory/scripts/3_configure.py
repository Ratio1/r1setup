#!/usr/bin/env python3

import os
import yaml
import getpass
import re
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class ConfigManager:
  def __init__(self):
    self.colors = {
      'red': '\033[91m',
      'green': '\033[92m',
      'yellow': '\033[93m',
      'blue': '\033[94m',
      'cyan': '\033[96m',
      'end': '\033[0m'
    }

    # Get the real user's home directory when running with sudo
    if 'SUDO_USER' in os.environ:
      import pwd
      real_user = os.environ['SUDO_USER']
      self.real_home = Path(pwd.getpwnam(real_user).pw_dir)
    else:
      self.real_home = Path.home()

    self.ratio1_base_dir = self.real_home / '.ratio1'
    self.ansible_config_root = self.ratio1_base_dir / 'ansible_config'
    # self.config_dir is where the collection is, and thus where hosts.yml should reside within it.
    self.config_dir = self.ansible_config_root / 'collections/ansible_collections/ratio1/multi_node_launcher'
    self.config_file = self.config_dir / 'hosts.yml'

    # Ensure the configuration directory exists (it should be created by 2_ansible_setup.sh's collection install)
    # Making sure it exists here is a fallback or for direct script use.
    self.config_dir.mkdir(parents=True, exist_ok=True)

    self.inventory = {
      'all': {
        'vars': {
          'mnl_app_env': 'mainnet'
        },
        'children': {
          'gpu_nodes': {
            'hosts': {}
          }
        }
      }
    }

  def print_colored(self, text: str, color: str = 'white') -> None:
    print(f"{self.colors.get(color, '')}{text}{self.colors['end']}")

  def get_input(self, prompt: str, default: str = '', required: bool = False) -> str:
    while True:
      default_str = f" [{default}]" if default else ""
      self.print_colored(f"{prompt}{default_str}: ", 'blue')
      value = input().strip() or default
      if required and not value:
        self.print_colored("This field cannot be empty. Please try again.", 'red')
        continue
      print()  # Add newline for spacing
      return value

  def get_secure_input(self, prompt: str) -> str:
    self.print_colored(prompt + ": ", 'blue')
    return getpass.getpass("")

  def validate_ip(self, ip: str) -> bool:
    """Validate IP address format"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
      return False
    return all(0 <= int(part) <= 255 for part in ip.split('.'))

  def get_ip_address(self) -> str:
    """Get and validate IP address"""
    while True:
      ip = self.get_input("Enter IP address", required=True)
      if self.validate_ip(ip):
        return ip
      self.print_colored("Invalid IP address format. Please use format: xxx.xxx.xxx.xxx", 'red')

  def select_mnl_app_env(self) -> str:
    """Select the network environment"""
    self.print_colored("\nChoose the network environment:", 'cyan')
    self.print_colored("1) mainnet")
    self.print_colored("2) testnet")
    self.print_colored("3) devnet")

    current_env = self.inventory.get('all', {}).get('vars', {}).get('mnl_app_env', 'mainnet')

    default_choice = '1'
    if current_env == 'testnet':
        default_choice = '2'
    elif current_env == 'devnet':
        default_choice = '3'

    self.print_colored(f"Current default is '{current_env}'.", 'yellow')

    network_env = ''
    while True:
        env_choice = self.get_input("Enter your choice (1-3)", default_choice)
        if env_choice == '1':
            network_env = 'mainnet'
            break
        elif env_choice == '2':
            network_env = 'testnet'
            break
        elif env_choice == '3':
            network_env = 'devnet'
            break
        else:
            self.print_colored("Invalid choice. Please enter 1, 2, or 3", 'red')
    
    self.print_colored(f"\n{network_env} network selected.", 'green')
    print()  # Add newline for spacing
    return network_env

  def configure_host(self, host_num: int) -> Dict[str, Any]:
    """Configure a single host"""
    while True:
      self.print_colored(f"\nConfiguring GPU Node #{host_num}", 'cyan')
      self.print_colored("------------------------", 'cyan')

      host = {}

      # Get basic connection info with validation
      host['ansible_host'] = self.get_ip_address()
      host['ansible_user'] = self.get_input("Enter SSH username", required=True)

      # Authentication method selection with numbered options
      self.print_colored("\nChoose authentication method:", 'cyan')
      self.print_colored("1) Password authentication")
      self.print_colored("2) SSH key authentication")

      while True:
        auth_choice = self.get_input("Enter your choice (1/2)", "2")
        if auth_choice in ['1', '2']:
          break
        self.print_colored("Invalid choice. Please enter 1 or 2", 'red')

      if auth_choice == '1':
        # Password authentication
        while True:
          ssh_pass = self.get_secure_input("Enter SSH password")
          if ssh_pass:
            host['ansible_ssh_pass'] = ssh_pass
            break
          self.print_colored("Password cannot be empty", 'red')

        sudo_pass = self.get_secure_input("Enter sudo password (press Enter if same as SSH)")
        host['ansible_become_password'] = sudo_pass or ssh_pass
      else:
        # Key authentication
        default_key = "~/.ssh/id_rsa"
        while True:
          key_path = self.get_input("Enter path to SSH private key", default_key)
          expanded_path = os.path.expanduser(key_path)
          if os.path.exists(expanded_path):
            host['ansible_ssh_private_key_file'] = key_path
            break
          self.print_colored(f"Key file not found: {expanded_path}", 'red')
          retry = self.get_input("Would you like to try another path? (y/n)", "y")
          if retry.lower() != 'y':
            self.print_colored("Please ensure the key file exists and try again", 'red')
            exit(1)

      # Add common SSH options
      host['ansible_ssh_common_args'] = '-o StrictHostKeyChecking=no'

      # Show configuration summary
      self.print_colored("\nConfiguration Summary:", 'yellow')
      self.print_colored(f"IP Address: {host['ansible_host']}", 'white')
      self.print_colored(f"Username: {host['ansible_user']}", 'white')
      self.print_colored(f"Auth Method: {'Password' if auth_choice == '1' else 'SSH Key'}", 'white')
      if auth_choice == '2':
        self.print_colored(f"SSH Key: {host['ansible_ssh_private_key_file']}", 'white')

      # Ask for confirmation
      confirm = self.get_input("\nAre you happy with this configuration? (y/n)", "y")
      if confirm.lower() == 'y':
        network_env = self.select_mnl_app_env()
        if 'vars' not in self.inventory['all']:
            self.inventory['all']['vars'] = {}
        self.inventory['all']['vars']['mnl_app_env'] = network_env
        self.save_hosts()
        return host

      self.print_colored("\nLet's configure this node again.", 'yellow')

  def edit_host(self, host_name: str, host_data: Dict[str, Any]) -> Dict[str, Any]:
    """Edit existing host configuration"""
    self.print_colored(f"\nEditing host: {host_name}", 'cyan')
    self.print_colored("Current configuration:", 'yellow')
    for key, value in host_data.items():
      if 'password' not in key and 'key' not in key:
        self.print_colored(f"{key}: {value}", 'white')

    options = {
      '1': 'IP address',
      '2': 'SSH username',
      '3': 'Authentication method',
      '4': 'Save and exit',
    }

    while True:
      self.print_colored("\nWhat would you like to edit?", 'cyan')
      for key, value in options.items():
        self.print_colored(f"{key}) {value}")

      choice = self.get_input("Enter your choice", "4")

      if choice == '1':
        host_data['ansible_host'] = self.get_ip_address()
      elif choice == '2':
        host_data['ansible_user'] = self.get_input("Enter SSH username", required=True)
      elif choice == '3':
        # Remove existing auth configuration
        for key in ['ansible_ssh_pass', 'ansible_become_password', 'ansible_ssh_private_key_file']:
          host_data.pop(key, None)

        auth_method = self.get_input("Choose authentication method (password/key)", "key")
        if auth_method.lower() == 'password':
          ssh_pass = self.get_secure_input("Enter SSH password")
          host_data['ansible_ssh_pass'] = ssh_pass
          sudo_pass = self.get_secure_input("Enter sudo password (press Enter if same as SSH)")
          host_data['ansible_become_password'] = sudo_pass or ssh_pass
        else:
          default_key = "~/.ssh/id_rsa"
          key_path = self.get_input("Enter path to SSH private key", default_key)
          host_data['ansible_ssh_private_key_file'] = os.path.expanduser(key_path)
      elif choice == '4':
        break

    return host_data

  def check_existing_config(self) -> bool:
    """Check for existing configuration and handle backup if needed"""
    if self.config_file.exists():
      self.print_colored("\nExisting configuration found!", 'yellow')
      self.print_colored(f"Configuration file: {self.config_file}", 'blue')
      self.print_colored("\nCurrent configuration:", 'cyan')

      # Read and display current configuration
      try:
        with open(self.config_file) as f:
          current_config = yaml.safe_load(f)
          if current_config and "all" in current_config:
            if "children" not in current_config["all"]:
              current_config["all"]["children"] = {'gpu_nodes': {'hosts': {}}}
            if "vars" not in current_config["all"]:
              current_config["all"]["vars"] = {}
              
            self.inventory = current_config
            hosts = current_config.get("all", {}).get("children", {}).get("gpu_nodes", {}).get("hosts", {})
            for host_name, host_config in hosts.items():
              self.print_colored(f"\nHost: {host_name}", 'yellow')
              for key, value in host_config.items():
                # Mask sensitive information
                if any(k in key.lower() for k in ["password", "key"]):
                  value = "********"
                self.print_colored(f"  {key}: {value}")

            network = self.inventory.get('all', {}).get('vars', {}).get('mnl_app_env', 'Not set')
            self.print_colored(f"\nNetwork Environment: {network}", 'yellow')

      except Exception as e:
        self.print_colored(f"Error reading current configuration: {str(e)}", 'red')

      # Instead of asking to overwrite, offer options to modify
      self.print_colored("\nWhat would you like to do with the existing configuration?", 'cyan')
      self.print_colored("1) Use and modify existing configuration")
      self.print_colored("2) Create a new configuration (backup existing)")
      self.print_colored("3) Exit without changes")
      
      choice = self.get_input("Enter your choice (1/2/3)", "1")
      
      if choice == "2":
        # Create history directory if it doesn't exist
        history_dir = self.config_dir / 'hosts-history'
        history_dir.mkdir(exist_ok=True)

        # Generate timestamp and backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = history_dir / f'hosts-{timestamp}.yml'

        # Backup existing configuration
        self.config_file.rename(backup_file)
        self.print_colored(f"Existing configuration backed up to: {backup_file}", 'green')
        
        # Reset inventory to empty
        self.inventory = {
          'all': {
            'vars': {
              'mnl_app_env': 'mainnet'
            },
            'children': {
              'gpu_nodes': {
                'hosts': {}
              }
            }
          }
        }
        return True
      elif choice == "3":
        self.print_colored("Exiting configuration script.", 'yellow')
        return False
      else:
        # Use existing configuration
        return True
    else:
      # No existing config, create a new one
      return True

  def add_host(self) -> None:
    """Add a new host to the configuration"""
    hosts = self.inventory['all']['children']['gpu_nodes']['hosts']
    host_count = len(hosts) + 1
    
    self.print_colored(f"\nAdding new GPU node #{host_count}", 'green')
    host_name = self.get_input(f"Enter name for new GPU node", f"gpu-node-{host_count}")
    
    # Check if host already exists
    if host_name in hosts:
      self.print_colored(f"A host with name '{host_name}' already exists!", 'red')
      overwrite = self.get_input("Do you want to overwrite it? (y/n)", "n")
      if overwrite.lower() != 'y':
        self.print_colored("Host addition cancelled.", 'yellow')
        return
    
    hosts[host_name] = self.configure_host(host_count)
    self.print_colored(f"\nGPU node '{host_name}' added successfully!", 'green')
    self.save_hosts()

  def delete_host(self) -> None:
    """Delete a host from the configuration"""
    hosts = self.inventory['all']['children']['gpu_nodes']['hosts']
    
    if not hosts:
      self.print_colored("No hosts configured yet!", 'red')
      return
    
    self.print_colored("\nSelect a host to delete:", 'cyan')
    for idx, name in enumerate(hosts.keys(), 1):
      self.print_colored(f"{idx}) {name}")
    
    choice = self.get_input("Enter host number to delete (or 'c' to cancel)", "c")
    if choice.lower() == 'c':
      self.print_colored("Host deletion cancelled.", 'yellow')
      return
    
    try:
      choice_idx = int(choice)
      if 1 <= choice_idx <= len(hosts):
        host_name = list(hosts.keys())[choice_idx - 1]
        confirm = self.get_input(f"Are you sure you want to delete host '{host_name}'? (y/n)", "n")
        if confirm.lower() == 'y':
          del hosts[host_name]
          self.print_colored(f"Host '{host_name}' deleted successfully!", 'green')
          self.save_hosts()
        else:
          self.print_colored("Host deletion cancelled.", 'yellow')
      else:
        self.print_colored("Invalid host number", 'red')
    except ValueError:
      self.print_colored("Invalid input", 'red')

  def update_host(self) -> None:
    """Update an existing host configuration"""
    hosts = self.inventory['all']['children']['gpu_nodes']['hosts']
    
    if not hosts:
      self.print_colored("No hosts configured yet!", 'red')
      return
    
    self.print_colored("\nSelect a host to update:", 'cyan')
    for idx, name in enumerate(hosts.keys(), 1):
      self.print_colored(f"{idx}) {name}")
    
    choice = self.get_input("Enter host number to update (or 'c' to cancel)", "c")
    if choice.lower() == 'c':
      self.print_colored("Host update cancelled.", 'yellow')
      return
    
    try:
      choice_idx = int(choice)
      if 1 <= choice_idx <= len(hosts):
        host_name = list(hosts.keys())[choice_idx - 1]
        hosts[host_name] = self.edit_host(host_name, hosts[host_name])
        self.print_colored(f"Host '{host_name}' updated successfully!", 'green')
        self.save_hosts()
      else:
        self.print_colored("Invalid host number", 'red')
    except ValueError:
      self.print_colored("Invalid input", 'red')

  def change_mnl_app_env(self) -> None:
    """Change the configured network environment."""
    network_env = self.select_mnl_app_env()
    if 'vars' not in self.inventory['all']:
        self.inventory['all']['vars'] = {}
    self.inventory['all']['vars']['mnl_app_env'] = network_env
    self.save_hosts()

  def show_configuration_menu(self) -> None:
    """Display the main configuration menu"""
    while True:
      self.print_colored("\n=======================", 'green')
      self.print_colored("Node Configuration Menu", 'green')
      self.print_colored("=======================", 'green')
      self.print_colored("1) View current configuration")
      self.print_colored("2) Add a new node")
      self.print_colored("3) Update an existing node")
      self.print_colored("4) Delete a node")
      self.print_colored("5) Change network environment")
      self.print_colored("6) Create a completely new configuration")
      self.print_colored("7) Save and exit")
      
      choice = self.get_input("Enter your choice (1-7)", "1")
      
      if choice == "1":
        self.view_configuration()
      elif choice == "2":
        self.add_host()
      elif choice == "3":
        self.update_host()
      elif choice == "4":
        self.delete_host()
      elif choice == "5":
        self.change_mnl_app_env()
      elif choice == "6":
        if self.create_new_configuration():
          self.setup_hosts_initial()
      elif choice == "7":
        self.print_colored("Configuration saved. Exiting...", 'green')
        self.print_colored("\nNext steps:", 'yellow')
        self.print_colored("1. Return to the setup menu", 'yellow')
        self.print_colored("2. Run deployment:", 'yellow')
        self.print_colored("   - Choose option 1 for full deployment (Docker + NVIDIA drivers + GPU setup)", 'cyan')
        self.print_colored("   - Choose option 2 for Docker-only deployment (without GPU setup)", 'cyan')
        break
      else:
        self.print_colored("Invalid choice. Please try again.", 'red')

  def view_configuration(self) -> None:
    """View the current configuration"""
    network_env = self.inventory.get('all', {}).get('vars', {}).get('mnl_app_env', 'Not set')
    self.print_colored(f"\nNetwork Environment: {network_env}", 'cyan')

    hosts = self.inventory['all']['children']['gpu_nodes']['hosts']
    
    if not hosts:
      self.print_colored("No hosts configured yet!", 'red')
      return
    
    self.print_colored("\nCurrent configuration:", 'cyan')
    for host_name, host_config in hosts.items():
      self.print_colored(f"\nHost: {host_name}", 'yellow')
      for key, value in host_config.items():
        # Mask sensitive information
        if any(k in key.lower() for k in ["password", "key"]):
          value = "********"
        self.print_colored(f"  {key}: {value}")
    
    input("\nPress Enter to continue...")

  def create_new_configuration(self) -> bool:
    """Create a completely new configuration, backing up any existing one"""
    if self.config_file.exists():
      confirm = self.get_input("This will overwrite your current configuration. Are you sure? (y/n)", "n")
      if confirm.lower() != 'y':
        self.print_colored("Operation cancelled.", 'yellow')
        return False
      
      # Create history directory if it doesn't exist
      history_dir = self.config_dir / 'hosts-history'
      history_dir.mkdir(exist_ok=True)

      # Generate timestamp and backup filename
      timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
      backup_file = history_dir / f'hosts-{timestamp}.yml'

      # Backup existing configuration
      self.config_file.rename(backup_file)
      self.print_colored(f"Existing configuration backed up to: {backup_file}", 'green')
    
    # Reset inventory to empty
    self.inventory = {
      'all': {
        'vars': {
          'mnl_app_env': 'mainnet'
        },
        'children': {
          'gpu_nodes': {
            'hosts': {}
          }
        }
      }
    }
    return True

  def setup_hosts_initial(self) -> None:
    """Initial host setup process for a new configuration"""
    network_env = self.select_mnl_app_env()
    if 'vars' not in self.inventory['all']:
        self.inventory['all']['vars'] = {}
    self.inventory['all']['vars']['mnl_app_env'] = network_env

    while True:
      try:
        num_hosts = int(self.get_input("How many GPU nodes do you want to configure"))
        if num_hosts <= 0:
          self.print_colored("Please enter a positive number", 'red')
          continue
        break
      except ValueError:
        self.print_colored("Please enter a valid number", 'red')

    hosts = self.inventory['all']['children']['gpu_nodes']['hosts']

    for i in range(num_hosts):
      host_name = self.get_input(f"Enter name for GPU node #{i + 1}", f"gpu-node-{i + 1}")
      hosts[host_name] = self.configure_host(i + 1)
      self.print_colored(f"\nGPU node '{host_name}' configured successfully!", 'green')
      self.print_colored("=" * 30, 'cyan')  # Divider
      print()  # Newline for spacing

    self.save_configuration()

  def setup_hosts(self) -> None:
    """Main host setup process with flexible configuration options"""
    self.print_colored("\n======================", 'green')
    self.print_colored("GPU Node Configuration", 'green')
    self.print_colored("======================", 'green')

    # Check for existing configuration
    if not self.check_existing_config():
      exit(0)

    # If we have an empty configuration, run the initial setup
    if not self.inventory['all']['children']['gpu_nodes']['hosts']:
      self.setup_hosts_initial()
    else:
      # For existing configurations, ensure network is set
      if 'mnl_app_env' not in self.inventory.get('all', {}).get('vars', {}):
        self.print_colored("\nNetwork environment is not set in the current configuration.", "yellow")
        self.change_mnl_app_env()
      # Otherwise, show the configuration menu
      self.show_configuration_menu()

  def save_configuration(self) -> None:
    """Save the configuration to file"""
    try:
      # Create directory with proper ownership if it doesn't exist
      self.config_dir.mkdir(parents=True, exist_ok=True)

      # Write the configuration
      with open(self.config_file, 'w') as f:
        yaml.safe_dump(self.inventory, f, default_flow_style=False)

      # Set proper permissions
      os.chmod(self.config_file, 0o600)

      self.print_colored("\nConfiguration completed successfully!", 'green')
      self.print_colored(f"Configuration saved to: {self.config_file}", 'blue')
      self.print_colored("\nNext steps:", 'yellow')
      self.print_colored("1. Return to the setup menu", 'yellow')
      self.print_colored("2. Run deployment:", 'yellow')
      self.print_colored("   - Choose option 1 for full deployment (Docker + NVIDIA drivers + GPU setup)", 'cyan')
      self.print_colored("   - Choose option 2 for Docker-only deployment (without GPU setup)", 'cyan')

    except Exception as e:
      self.print_colored(f"Error saving configuration: {str(e)}", 'red')
      exit(1)

  def save_hosts(self) -> None:
    """Save the hosts configuration to the YAML file."""
    with open(self.config_file, 'w') as f:
      yaml.safe_dump(self.inventory, f, default_flow_style=False)
    print(f"{self.colors['green']}Configuration saved to: {self.config_file}{self.colors['end']}")


def main():
  config_manager = ConfigManager()
  config_manager.setup_hosts()


if __name__ == "__main__":
  main()