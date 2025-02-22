#!/bin/bash

INSTALLER_VERSION="0.0.1"

log_with_color() {
  local text="$1"
  local color="$2"
  local color_code=""

  case $color in
    red)
      color_code="0;31" # Red
      ;;
    green)
      color_code="0;32" # Green
      ;;
    blue)
      color_code="0;34" # Blue
      ;;
    yellow)
      color_code="0;33" # Yellow
      ;;
    light)
      color_code="1;37" # Light (White)
      ;;
    gray)
      color_code="2;37" # Gray (White)
      ;;
    *)
      color_code="0" # Default color
      ;;
  esac

  # Check if terminal supports colors
  if [[ -t 1 ]]; then
    echo -e "\e[${color_code}m${text}\e[0m"
  else
    echo "${text}"
  fi
}

# Function to get OS information
get_os_info() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=${NAME:-"Unknown"}
    OS_VERSION=${VERSION:-"Unknown"}
  elif type "sw_vers" &> /dev/null; then
    OS_NAME="macOS"
    OS_VERSION=$(sw_vers -productVersion)
  else
    log_with_color "Unsupported OS" red
    exit 1
  fi
}

check_if_os_accepted() {
  ACCEPTED_OS=("Ubuntu" "Debian" "CentOS" "Red Hat Enterprise Linux" "Fedora" "Oracle Linux Server")
  get_os_info
  log_with_color "Operating System: $OS_NAME" 
  log_with_color "Version: $OS_VERSION"

  if [[ ! " ${ACCEPTED_OS[*]} " =~ " $OS_NAME " ]]; then
    log_with_color "This script runs only on ${ACCEPTED_OS[*]}. Exiting." red
    exit 1
  fi

  log_with_color "$OS_NAME:$OS_VERSION is supported." green
}

# Determine package manager and set installation functions
determine_package_manager() {
  if command -v apt-get &> /dev/null; then
    PACKAGE_MANAGER="apt-get"
    UPDATE_CMD="sudo apt-get update"
    INSTALL_CMD="sudo apt-get install -y"
  elif command -v yum &> /dev/null; then
    PACKAGE_MANAGER="yum"
    UPDATE_CMD="sudo yum update -y"
    INSTALL_CMD="sudo yum install -y"
  else
    log_with_color "Unsupported package manager. Exiting." red
    exit 1
  fi
}

# Function to install a package
install_package() {
  local package="$1"
  log_with_color "Installing $package..." yellow
  $UPDATE_CMD
  $INSTALL_CMD $package
  if [ $? -ne 0 ]; then
    log_with_color "Failed to install $package. Exiting." red
    exit 1
  fi
}

# Function to install Python
install_python() {
  install_package "python3"
}

# Function to install Pip
install_pip() {
  install_package "python3-pip"
}

# Function to install sshpass
install_sshpass() {
  if [ "$PACKAGE_MANAGER" == "yum" ]; then
    install_package "epel-release"
  fi
  install_package "sshpass"
}

# Function to install Ansible
install_ansible() {
  log_with_color "Installing Ansible..." yellow
  pip3 install ansible --upgrade
  if [ $? -ne 0 ]; then
    log_with_color "Failed to install Ansible. Exiting." red
    exit 1
  fi
}

# Parse command-line arguments
SKIP_INSTALLATIONS=false
for arg in "$@"; do
  case $arg in
    --skip)
      SKIP_INSTALLATIONS=true
      shift
      ;;
    *)
      ;;
  esac
done

# Check for sudo privileges if installations are not skipped
if [ "$SKIP_INSTALLATIONS" = false ]; then
  if ! sudo -v; then
    log_with_color "This script requires sudo privileges. Please run as a user with sudo access." red
    exit 1
  fi
fi

## SCRIPT STARTS HERE
log_with_color "########    Starting MNL Factory setup v.$INSTALLER_VERSION ...    ########" green

check_if_os_accepted
determine_package_manager

# Create a directory for the factory
mkdir -p factory
cd factory

path_to_add="$HOME/.local/bin"
export PATH="$PATH:$path_to_add"

curr_dir1=$(pwd)


if [ "$SKIP_INSTALLATIONS" = false ]; then


  # Check if sshpass is installed
  if ! command -v sshpass &> /dev/null; then
    log_with_color "sshpass is not installed." yellow
    install_sshpass
  else
    log_with_color "sshpass is already installed." green
  fi

  # Check if Python is installed
  if ! command -v python3 &> /dev/null; then
    install_python
  else
    log_with_color "Python is already installed." green
  fi

  # Check if Pip is installed
  if ! command -v pip3 &> /dev/null; then
    install_pip
  else
    log_with_color "Pip is already installed." green
  fi

  # Check if Ansible is installed
  if ! ansible --version &> /dev/null; then
    log_with_color "Ansible is not installed. Installing..." yellow
    install_ansible

    if ! grep -q "$path_to_add" ~/.bashrc; then
      log_with_color "Adding $path_to_add to .bashrc" yellow
      echo "export PATH=\"\$PATH:$path_to_add\"" >> ~/.bashrc
      log_with_color "$path_to_add added to .bashrc and reloaded" green
    else
      log_with_color "Path $path_to_add already in .bashrc" green
    fi
  else
    log_with_color "Ansible is already installed." green
  fi
fi

# Install Ansible Collection
log_with_color "Installing Ansible Collection: vitalii_t12.multi_node_launcher" light
ansible-galaxy collection install vitalii_t12.multi_node_launcher --force

if [ $? -eq 0 ]; then
  COLLECTION_VER=$(ansible-galaxy collection list | grep vitalii_t12.multi_node_launcher | awk '{print $2}')
  log_with_color " " 
  log_with_color "Ansible Collection: vitalii_t12.multi_node_launcher v$COLLECTION_VER is successfully installed." green
  log_with_color "___________________________________________________________________________" green
else
  log_with_color "Ansible Collection: vitalii_t12.multi_node_launcher is not installed." red
  exit 1
fi

# Define the path to the collection
collection_path="$HOME/.ratio1/.multi-node-launcher/collections/ansible_collections/multi_node_launcher"

# check if a parameter is passed to the script and if it is "r1"
if [ "$1" == "r1" ]; then
  # Copy .hosts.yml from the collection to the current directory
  log_with_color "Copying .nen.yml from the collection to factory .hosts.yml" blue
  cp "${collection_path}/other/.nen.yml" ./.hosts.yml
else
  # Copy .hosts.yml from the collection to the current directory
  log_with_color "Copying .hosts.yml from the collection to factory .hosts.yml" blue
  cp "${collection_path}/other/.hosts.yml" ./.hosts.yml
fi



if [ ! -f "./hosts.yml" ]; then
  log_with_color "Copying .hosts.yml from the collection to hosts.yml for edit" blue
  cp "./.hosts.yml" ./hosts.yml
else
  log_with_color "hosts.yml already exists. Not copying." blue
fi

log_with_color "***********************************************************************************" yellow
log_with_color "********                                                                   ********" yellow
log_with_color "********  Please modify the ./factory/hosts.yml file with your own values  ********" yellow
log_with_color "********                                                                   ********" yellow
log_with_color "***********************************************************************************" yellow

# Copy ansible.cfg from the collection to the current directory
if [ ! -f "./ansible.cfg" ]; then
  log_with_color "Copying ansible.cfg to $curr_dir1"
  cp "${collection_path}/other/ansible.cfg" ./ansible.cfg
else
  log_with_color "ansible.cfg already exists. Overwriting..." yellow
  cp "${collection_path}/other/ansible.cfg" ./ansible.cfg
fi

# Create empty key.pem file if it does not exist
if [ ! -f "./key.pem" ]; then
  log_with_color "Creating empty key.pem file"
  touch key.pem    
  log_with_color "********  Please write a SK in the key.pem file  ********" yellow
else
  log_with_color "key.pem already exists. Not creating." green
fi

chmod 600 key.pem

# Copy deploy.yml from the collection to the current directory
if [ ! -f "./deploy.yml" ]; then
  log_with_color "Copying deploy.yml to $curr_dir1" blue
  cp "${collection_path}/other/deploy.yml" ./deploy.yml
else
  log_with_color "deploy.yml already exists in $curr_dir1. Overwriting..." yellow
  cp "${collection_path}/other/deploy.yml" ./deploy.yml
fi

# Copy deploy-gpu.yml from the collection to the current directory
if [ ! -f "./deploy-gpu.yml" ]; then
  log_with_color "Copying deploy-gpu.yml to $curr_dir1" blue
  cp "${collection_path}/other/deploy-gpu.yml" ./deploy-gpu.yml
else
  log_with_color "deploy-gpu.yml already exists in $curr_dir1. Overwriting..." yellow
  cp "${collection_path}/other/deploy-gpu.yml" ./deploy-gpu.yml
fi

# Copy deploy-config.yml from the collection to the current directory
if [ ! -f "./deploy-config.yml" ]; then
  log_with_color "Copying deploy-config.yml to $curr_dir1" blue
  cp "${collection_path}/other/deploy-config.yml" ./deploy-config.yml
else
  log_with_color "deploy-config.yml already exists in $curr_dir1. Overwriting..." yellow
  cp "${collection_path}/other/deploy-config.yml" ./deploy-config.yml
fi

# Move from factory to parent folder
cd ..

curr_dir2=$(pwd)

log_with_color "Checking main run.sh script in $curr_dir2" blue

# Copy run.sh from the collection to the current directory
if [ ! -f "./run.sh" ]; then
  log_with_color "Copying run.sh from the collection to current directory $curr_dir2." blue
  cp "${collection_path}/other/run.sh" ./run.sh
else
  log_with_color "run.sh already exists in $curr_dir2. Overwriting..." yellow
  cp "${collection_path}/other/run.sh" ./run.sh
fi

# Copy run-gpu-only.sh from the collection to the current directory
if [ ! -f "./run-gpu-only.sh" ]; then
  log_with_color "Copying run-gpu-only.sh from the collection to current directory $curr_dir2." blue
  cp "${collection_path}/other/run-gpu-only.sh" ./run-gpu-only.sh
else
  log_with_color "run-gpu-only.sh already exists in $curr_dir2. Overwriting..." yellow
  cp "${collection_path}/other/run-gpu-only.sh" ./run-gpu-only.sh
fi

# Copy run-config.sh from the collection to the current directory
if [ ! -f "./run-config.sh" ]; then
  log_with_color "Copying run-config.sh from the collection to current directory $curr_dir2."
  cp "${collection_path}/other/run-config.sh" ./run-config.sh
else
  log_with_color "run-config.sh already exists in $curr_dir2. Overwriting..." yellow
  cp "${collection_path}/other/run-config.sh" ./run-config.sh
fi

# Copy showlog.sh from the collection to the current directory
if [ ! -f "./showlog.sh" ]; then
  log_with_color "Copying showlog.sh from the collection to current directory $curr_dir2."
  cp "${collection_path}/other/showlog.sh" ./showlog.sh
else
  log_with_color "showlog.sh already exists in $curr_dir2. Overwriting..." yellow
  cp "${collection_path}/other/showlog.sh" ./showlog.sh
fi

chmod +x run.sh
chmod +x run-gpu-only.sh
chmod +x run-config.sh
chmod +x showlog.sh
log_with_color "Done setting up the factory." green
log_with_color "Edit 'nano ./factory/hosts.yml' and enter your hosts and setup ./factory/key.pem or assign a already existing ~/.ssh .pem file" yellow
log_with_color "You can use ./run-gpu-only.sh to setup only the GPU on target hosts" yellow
log_with_color "Launch the deploy process with ./run.sh" green
log_with_color "Setup Completed." green
