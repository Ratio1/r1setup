#!/usr/bin/env python3

import os
import sys
import yaml
import socket
import getpass
import platform
import ipaddress
from typing import Dict, Any, List, Optional, Tuple

class ConfigManager:
    def __init__(self):
        self.colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'purple': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'end': '\033[0m'
        }
        
        # Detect OS
        self.os_type = platform.system().lower()
        print(f"{self.colors['green']}Detected OS: {self.os_type.capitalize()}{self.colors['end']}")

        self.base_dir = os.path.expanduser("~/.ratio1/multi-node-launcher")
        self.ansible_dir = os.path.expanduser("~/.ansible")
        # # Set base directories based on OS
        # if self.os_type == 'darwin':  # macOS
        #     # Use user's home directory for macOS
        #     self.base_dir = os.path.expanduser("~/multi-node-launcher")
        #     self.ansible_dir = os.path.expanduser("~/.ansible")
        # else:  # Linux and others
        #     # Use /opt for Linux
        #     self.base_dir = "/opt/multi-node-launcher"
        #     self.ansible_dir = os.path.expanduser("~/.ansible")
        
        # Derived paths
        self.collection_path = os.path.join(self.ansible_dir, "collections/ansible_collections/ratio1/multi_node_launcher")
        self.hosts_file = os.path.join(self.collection_path, "hosts.yml")
        self.factory_dir = os.path.join(self.base_dir, "factory")
        self.local_hosts_file = os.path.join(self.factory_dir, "hosts.yml")
        
        # Create directories if they don't exist
        os.makedirs(self.factory_dir, exist_ok=True)
        
        # Initialize configuration
        self.config = {
            'all': {
                'children': {
                    'gpu_nodes': {
                        'hosts': {}
                    }
                }
            }
        }
    
    def print_colored(self, text: str, color: str = 'white') -> None:
        print(f"{self.colors.get(color, self.colors['white'])}{text}{self.colors['end']}")
    
    def get_input(self, prompt: str, default: str = '', required: bool = False) -> str:
        prompt_text = f"{prompt} [{default}]: " if default else f"{prompt}: "
        while True:
            value = input(prompt_text).strip()
            if not value and default:
                return default
            if not value and required:
                self.print_colored("This field is required!", 'red')
                continue
            return value
    
    def get_secure_input(self, prompt: str) -> str:
        return getpass.getpass(prompt + ": ")
    
    def validate_ip(self, ip: str) -> bool:
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def get_ip_address(self) -> str:
        # Try to get the default IP address of the system
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            default_ip = s.getsockname()[0]
            s.close()
        except:
            default_ip = "127.0.0.1"
        
        return default_ip
    
    def configure_host(self, host_num: int) -> Dict[str, Any]:
        self.print_colored(f"\n=== Configuring GPU Host #{host_num} ===", 'cyan')
        
        host_name = self.get_input("Host name (e.g., gpu-node-1)", f"gpu-node-{host_num}", True)
        
        # Get connection details
        ip_address = self.get_input("IP address", self.get_ip_address(), True)
        while not self.validate_ip(ip_address):
            self.print_colored("Invalid IP address format!", 'red')
            ip_address = self.get_input("IP address", self.get_ip_address(), True)
        
        port = self.get_input("SSH port", "22")
        username = self.get_input("SSH username", os.getlogin())
        
        # Authentication options
        auth_type = self.get_input("Authentication type (password/key)", "password")
        
        if auth_type.lower() == 'password':
            password = self.get_secure_input("SSH password")
            host_data = {
                'ansible_host': ip_address,
                'ansible_port': port,
                'ansible_user': username,
                'ansible_ssh_pass': password,
                'ansible_become_pass': password
            }
        else:
            # Key-based authentication
            # Check common key locations based on OS
            if self.os_type == 'darwin':
                default_key_path = os.path.expanduser("~/.ssh/id_rsa")
            else:
                default_key_path = os.path.expanduser("~/.ssh/id_rsa")
                
            key_path = self.get_input("SSH private key path", default_key_path)
            
            host_data = {
                'ansible_host': ip_address,
                'ansible_port': port,
                'ansible_user': username,
                'ansible_ssh_private_key_file': os.path.expanduser(key_path)
            }
            
            # Ask for sudo password if needed
            if self.get_input("Does this user require a password for sudo? (y/n)", "y").lower() == 'y':
                become_pass = self.get_secure_input("Sudo password")
                host_data['ansible_become_pass'] = become_pass
        
        # Automatically configure all GPUs without asking
        host_data['gpu_count'] = 'all'  # This will tell Ansible to use all available GPUs
        
        return {host_name: host_data}
    
    def edit_host(self, host_name: str, host_data: Dict[str, Any]) -> Dict[str, Any]:
        self.print_colored(f"\n=== Editing Host {host_name} ===", 'cyan')
        
        # Show current configuration
        self.print_colored("Current configuration:", 'yellow')
        for key, value in host_data.items():
            # Mask sensitive information
            if 'pass' in key or 'key' in key:
                print(f"  {key}: ********")
            else:
                print(f"  {key}: {value}")
        
        # IP address
        ip_address = self.get_input("IP address", host_data.get('ansible_host', ''))
        while ip_address and not self.validate_ip(ip_address):
            self.print_colored("Invalid IP address format!", 'red')
            ip_address = self.get_input("IP address", host_data.get('ansible_host', ''))
        
        if ip_address:
            host_data['ansible_host'] = ip_address
        
        # Port
        port = self.get_input("SSH port", host_data.get('ansible_port', '22'))
        if port:
            host_data['ansible_port'] = port
        
        # Username
        username = self.get_input("SSH username", host_data.get('ansible_user', ''))
        if username:
            host_data['ansible_user'] = username
        
        # Authentication
        if 'ansible_ssh_pass' in host_data:
            if self.get_input("Change SSH password? (y/n)", "n").lower() == 'y':
                password = self.get_secure_input("New SSH password")
                host_data['ansible_ssh_pass'] = password
                host_data['ansible_become_pass'] = password
        elif 'ansible_ssh_private_key_file' in host_data:
            if self.get_input("Change SSH key path? (y/n)", "n").lower() == 'y':
                key_path = self.get_input("SSH private key path", host_data.get('ansible_ssh_private_key_file', ''))
                host_data['ansible_ssh_private_key_file'] = os.path.expanduser(key_path)
            
            if self.get_input("Change sudo password? (y/n)", "n").lower() == 'y':
                become_pass = self.get_secure_input("Sudo password")
                host_data['ansible_become_pass'] = become_pass
        
        # Ensure GPU configuration is set to use all GPUs
        host_data['gpu_count'] = 'all'
        
        return {host_name: host_data}
    
    def check_existing_config(self) -> bool:
        """Check for existing configuration and offer to load it"""
        config_files = [self.hosts_file, self.local_hosts_file]
        existing_config = None
        config_path = None
        
        for file_path in config_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        config_data = yaml.safe_load(f)
                        if config_data and 'all' in config_data and 'children' in config_data['all']:
                            existing_config = config_data
                            config_path = file_path
                            break
                except Exception as e:
                    self.print_colored(f"Error reading {file_path}: {str(e)}", 'red')
        
        if existing_config:
            self.print_colored(f"Found existing configuration at {config_path}", 'green')
            load_existing = self.get_input("Do you want to load this configuration? (y/n)", "y")
            
            if load_existing.lower() == 'y':
                self.config = existing_config
                
                # Show hosts
                hosts = existing_config['all']['children']['gpu_nodes']['hosts']
                if hosts:
                    self.print_colored("\nExisting hosts:", 'cyan')
                    for host, data in hosts.items():
                        ip = data.get('ansible_host', 'Unknown IP')
                        user = data.get('ansible_user', 'Unknown user')
                        self.print_colored(f"  {host} ({ip}, {user})", 'yellow')
                
                # Ask to edit
                edit_config = self.get_input("Do you want to edit this configuration? (y/n)", "n")
                if edit_config.lower() == 'y':
                    self.setup_hosts()
                
                return True
        
        return False
    
    def setup_hosts(self) -> None:
        """Configure hosts for the deployment"""
        self.print_colored("\n=== Host Configuration ===", 'blue')
        
        # Check if we have existing hosts
        existing_hosts = self.config['all']['children']['gpu_nodes']['hosts']
        if existing_hosts:
            self.print_colored("Current hosts:", 'cyan')
            for idx, (host, data) in enumerate(existing_hosts.items(), 1):
                ip = data.get('ansible_host', 'Unknown IP')
                user = data.get('ansible_user', 'Unknown user')
                self.print_colored(f"  {idx}. {host} ({ip}, {user})", 'yellow')
            
            print("\nOptions:")
            print("  a: Add a new host")
            print("  e: Edit an existing host")
            print("  d: Delete a host")
            print("  c: Continue with current hosts")
            
            action = self.get_input("Select an option", "c")
            
            if action.lower() == 'a':
                # Add a new host
                host_num = len(existing_hosts) + 1
                new_host = self.configure_host(host_num)
                self.config['all']['children']['gpu_nodes']['hosts'].update(new_host)
                self.setup_hosts()  # Recursive call to continue setup
            
            elif action.lower() == 'e':
                # Edit an existing host
                host_idx = int(self.get_input("Enter the number of the host to edit", "1"))
                if 1 <= host_idx <= len(existing_hosts):
                    host_name = list(existing_hosts.keys())[host_idx - 1]
                    host_data = existing_hosts[host_name]
                    updated_host = self.edit_host(host_name, host_data)
                    self.config['all']['children']['gpu_nodes']['hosts'].update(updated_host)
                else:
                    self.print_colored("Invalid host number!", 'red')
                self.setup_hosts()  # Recursive call to continue setup
            
            elif action.lower() == 'd':
                # Delete a host
                host_idx = int(self.get_input("Enter the number of the host to delete", "1"))
                if 1 <= host_idx <= len(existing_hosts):
                    host_name = list(existing_hosts.keys())[host_idx - 1]
                    confirm = self.get_input(f"Are you sure you want to delete {host_name}? (y/n)", "n")
                    if confirm.lower() == 'y':
                        del self.config['all']['children']['gpu_nodes']['hosts'][host_name]
                        self.print_colored(f"Host {host_name} deleted!", 'green')
                else:
                    self.print_colored("Invalid host number!", 'red')
                self.setup_hosts()  # Recursive call to continue setup
        else:
            # No existing hosts, add a new one
            self.print_colored("No hosts configured yet.", 'yellow')
            add_host = self.get_input("Do you want to add a host? (y/n)", "y")
            
            if add_host.lower() == 'y':
                new_host = self.configure_host(1)
                self.config['all']['children']['gpu_nodes']['hosts'].update(new_host)
                
                # Ask if user wants to add more hosts
                add_more = self.get_input("Do you want to add another host? (y/n)", "n")
                if add_more.lower() == 'y':
                    self.setup_hosts()  # Recursive call to continue setup
    
    def save_configuration(self) -> None:
        """Save the configuration to hosts files"""
        if not self.config['all']['children']['gpu_nodes']['hosts']:
            self.print_colored("No hosts configured! Cannot save empty configuration.", 'red')
            return
        
        try:
            # Save to the collection path
            os.makedirs(os.path.dirname(self.hosts_file), exist_ok=True)
            with open(self.hosts_file, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            
            # Save to factory directory for easy access
            os.makedirs(os.path.dirname(self.local_hosts_file), exist_ok=True)
            with open(self.local_hosts_file, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
            
            # Set appropriate permissions (more restrictive because it contains credentials)
            if self.os_type != 'darwin':  # chmod works differently on macOS
                os.chmod(self.hosts_file, 0o600)
                os.chmod(self.local_hosts_file, 0o600)
            
            # If symlink doesn't exist, create it
            factory_hosts = os.path.join(self.factory_dir, "hosts.yml")
            if not os.path.exists(factory_hosts):
                if self.os_type == 'darwin':
                    # For macOS, copy instead of symlink (can be more reliable)
                    with open(factory_hosts, 'w') as f:
                        yaml.dump(self.config, f, default_flow_style=False)
                else:
                    # For Linux, create a symlink
                    if os.path.exists(factory_hosts):
                        os.remove(factory_hosts)
                    os.symlink(self.hosts_file, factory_hosts)
            
            self.print_colored("Configuration saved successfully!", 'green')
            self.print_colored(f"Hosts file: {self.hosts_file}", 'cyan')
            self.print_colored(f"Local copy: {self.local_hosts_file}", 'cyan')
            
        except Exception as e:
            self.print_colored(f"Error saving configuration: {str(e)}", 'red')
            
    def save_hosts(self) -> None:
        """Wrapper for save_configuration"""
        self.save_configuration()

def main():
    config_manager = ConfigManager()
    
    print("\n")
    print("=" * 60)
    print(" Multi-Node Launcher Configuration Tool ".center(60, '='))
    print("=" * 60)
    print("\n")
    
    # Check for existing configuration
    if not config_manager.check_existing_config():
        # Setup hosts if no existing configuration or user wants to reconfigure
        config_manager.setup_hosts()
    
    # Save configuration
    config_manager.save_hosts()
    
    print("\n")
    print("=" * 60)
    print(" Configuration Complete ".center(60, '='))
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Run the setup script:")
    if config_manager.os_type == 'darwin':
        print(f"   source {config_manager.base_dir}/activate_env.sh")
    else:
        print("   source /opt/multi-node-launcher/activate_env.sh")
    print("2. Run the deployment:")
    print("   ansible-playbook deploy.yml")
    print("\n")

if __name__ == "__main__":
    main()