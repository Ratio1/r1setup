#!/bin/bash

# Ratio1 Multi-Node Launcher Setup - System Wrapper
# This script calls the actual r1setup script from the user's .ratio1 directory

# Get the real user's home directory (handles sudo scenarios)
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
    if [ "$(uname)" = "Darwin" ]; then
        REAL_HOME=$(dscl . -read /Users/"$SUDO_USER" NFSHomeDirectory | awk '{print $2}')
    else
        REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    fi
else
    REAL_USER="$USER"
    REAL_HOME="$HOME"
fi

# Path to the actual r1setup script
R1SETUP_SCRIPT="$REAL_HOME/.ratio1/r1_setup_scripts/r1setup"

# Check if the script exists
if [ ! -f "$R1SETUP_SCRIPT" ]; then
    echo "ERROR: r1setup script not found at: $R1SETUP_SCRIPT"
    echo "Please ensure the Ratio1 Multi-Node Launcher is properly installed."
    echo "Run the install-factory script to install or reinstall."
    exit 1
fi

# Execute the actual r1setup script with all provided arguments
exec python3 "$R1SETUP_SCRIPT" "$@" 