#!/bin/bash

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
        *)
            color_code="0" # Default color
            ;;
    esac

    echo -e "\e[${color_code}m${text}\e[0m"
}

log_with_color "Deleting any .tar.gz files in the current directory..." blue

# finds, displays and deletes all .tar.gz files in the current directory
find . -name "*.tar.gz" -type f -print -delete

# Load ANSIBLE_TOKEN from .env file
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | awk '/=/ {print $1}')
else
    log_with_color ".env file not found" red
    exit 1
fi

# Check if ANSIBLE_TOKEN is set
if [ -z "$ANSIBLE_TOKEN" ]; then
    log_with_color "ANSIBLE_TOKEN is not set. Please set it in the .env file." red
    exit 1
fi

log_with_color "Using token $ANSIBLE_TOKEN" blue

# Building the collection
log_with_color "Building the Ansible collection..." 
ansible-galaxy collection build

# Check if build was successful
if [ $? -ne 0 ]; then
    log_with_color "Failed to build the collection." red
    exit 1
fi

log_with_color "Done building the Ansible collection." green 

# Publishing the collection
log_with_color "Publishing the collection..."
ansible-galaxy collection publish ./*.tar.gz --api-key $ANSIBLE_TOKEN

# Check if publish was successful
if [ $? -ne 0 ]; then
    log_with_color "Failed to publish the collection." red
    exit 1
fi

log_with_color "Collection published successfully." green

log_with_color "Deleting any .tar.gz files in the current directory..." blue
# finds, displays and deletes all .tar.gz files in the current directory
find . -name "*.tar.gz" -type f -print -delete
