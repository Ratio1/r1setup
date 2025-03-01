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
            
        self.config_dir = self.real_home / '.ansible/collections/ansible_collections/ratio1/multi_node_launcher'
        self.config_file = self.config_dir / 'hosts.yml'
        
        # Ensure the configuration directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.inventory = {
            'all': {
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
                    if current_config and "all" in current_config and "children" in current_config["all"]:
                        hosts = current_config["all"]["children"]["gpu_nodes"]["hosts"]
                        for host_name, host_config in hosts.items():
                            self.print_colored(f"\nHost: {host_name}", 'yellow')
                            for key, value in host_config.items():
                                # Mask sensitive information
                                if any(k in key.lower() for k in ["password", "key"]):
                                    value = "********"
                                self.print_colored(f"  {key}: {value}")
            except Exception as e:
                self.print_colored(f"Error reading current configuration: {str(e)}", 'red')

            overwrite = self.get_input("\nDo you want to create a new configuration? (y/n)", "n")
            
            if overwrite.lower() == 'y':
                # Create history directory if it doesn't exist
                history_dir = self.config_dir / 'hosts-history'
                history_dir.mkdir(exist_ok=True)
                
                # Generate timestamp and backup filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_file = history_dir / f'hosts-{timestamp}.yml'
                
                # Backup existing configuration
                self.config_file.rename(backup_file)
                self.print_colored(f"Existing configuration backed up to: {backup_file}", 'green')
                return True
            else:
                self.print_colored("Exiting configuration script.", 'yellow')
                return False
        return True

    def setup_hosts(self) -> None:
        """Main host setup process"""
        self.print_colored("\nGPU Node Configuration", 'green')
        self.print_colored("===================", 'green')

        # Check for existing configuration
        if not self.check_existing_config():
            exit(0)

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
            host_name = self.get_input(f"Enter name for GPU node #{i+1}", f"gpu-node-{i+1}")
            hosts[host_name] = self.configure_host(i+1)
            self.print_colored(f"\nGPU node '{host_name}' configured successfully!", 'green')
            self.print_colored("=" * 30, 'cyan')  # Divider
            print()  # Newline for spacing

        # Allow editing after all hosts are configured
        while True:
            self.print_colored("\nCurrent configuration:", 'cyan')
            for idx, (name, config) in enumerate(hosts.items(), 1):
                self.print_colored(f"\n{idx}) {name}:", 'yellow')
                for key, value in config.items():
                    if 'password' not in key and 'key' not in key:
                        self.print_colored(f"   {key}: {value}")

            edit = self.get_input("\nWould you like to edit any host? (Enter host number or 'n' to finish)", "n")
            if edit.lower() == 'n':
                break

            try:
                edit_idx = int(edit)
                if 1 <= edit_idx <= len(hosts):
                    host_name = list(hosts.keys())[edit_idx - 1]
                    hosts[host_name] = self.edit_host(host_name, hosts[host_name])
                else:
                    self.print_colored("Invalid host number", 'red')
            except ValueError:
                self.print_colored("Invalid input", 'red')

        self.save_configuration()

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
            
            # Set proper ownership if running with sudo
            if 'SUDO_USER' in os.environ:
                import pwd
                import grp
                real_user = os.environ['SUDO_USER']
                uid = pwd.getpwnam(real_user).pw_uid
                gid = pwd.getpwnam(real_user).pw_gid
                os.chown(self.config_file, uid, gid)
                # Also set ownership of the config directory
                for root, dirs, files in os.walk(str(self.config_dir)):
                    os.chown(root, uid, gid)
                    for d in dirs:
                        os.chown(os.path.join(root, d), uid, gid)
                    for f in files:
                        os.chown(os.path.join(root, f), uid, gid)

            self.print_colored("\nConfiguration completed successfully!", 'green')
            self.print_colored(f"Configuration saved to: {self.config_file}", 'blue')
            self.print_colored("\nNext steps:", 'yellow')
            self.print_colored("1. Review your configuration:", 'yellow')
            self.print_colored(f"   cat {self.config_file}", 'blue')
            self.print_colored("2. Run the setup script:", 'yellow')
            self.print_colored("   ./3_run_setup.sh", 'blue')

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