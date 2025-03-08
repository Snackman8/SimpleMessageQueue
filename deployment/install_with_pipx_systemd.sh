#!/bin/bash

# ----------------------------------------
#   General Configuration
# ----------------------------------------
APP_NAME=SimpleMessageQeue
SERVICE_NAME=SimpleMessageQueue.service
# location where all pipx apps are installed
PIPX_HOME_DIR="/usr/local/pipx"


# ----------------------------------------
#   PipX Configuration
# ----------------------------------------
# Check if pipx is installed
if ! command -v pipx &> /dev/null; then
    echo "Error: pipx is not installed."
    exit 1
fi

# Find the full path of the pipx binary
PIPX_BIN=$(command -v pipx)

# Extract the directory containing pipx
PIPX_BIN_DIR=$(dirname "$PIPX_BIN")

# Check if we successfully got the directory
if [[ -z "$PIPX_BIN_DIR" ]]; then
    echo "Error: Could not determine pipx binary directory."
    exit 1
fi


# ----------------------------------------
#   Uninstall
# ----------------------------------------
if [[ "$1" == "--uninstall" ]]; then
    echo "Uninstalling ${APP_NAME}..."

    echo "Stopping and disabling systemd service..."
    sudo systemctl stop $SERVICE_NAME
    sudo systemctl disable $SERVICE_NAME

    echo "Removing systemd service file..."
    sudo rm -f $SYSTEMD_PATH
    sudo systemctl daemon-reload

    echo "Uninstalling the app using pipx..."
    sudo PIPX_HOME=$PIPX_HOME_DIR PIPX_BIN_DIR=$PIPX_BIN_DIR ${PIPX_BIN_DIR}/pipx uninstall ${APP_NAME}

    echo "Uninstallation complete."
    exit 0
fi


# ----------------------------------------
#   Install
# ----------------------------------------
echo "Installing ${APP_NAME} using pipx..."
sudo PIPX_HOME=$PIPX_HOME_DIR PIPX_BIN_DIR=$PIPX_BIN_DIR ${PIPX_BIN_DIR}/pipx install .. --include-deps

echo "Copying systemd service file..."
sudo cp $SERVICE_NAME /etc/systemd/system/

echo "Setting correct permissions for the service file..."
sudo chmod 644 /etc/systemd/system/$SERVICE_NAME

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling and starting the service..."
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "Installation of ${APP_NAME} complete."
