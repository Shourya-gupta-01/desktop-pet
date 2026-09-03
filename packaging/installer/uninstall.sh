#!/usr/bin/env bash
set -e

INSTALL_PREFIX="${HOME}/.local/share/desktop-pet"
BIN_DIR="${HOME}/.local/bin"
AUTOSTART_DIR="${HOME}/.config/autostart"
APPS_DIR="${HOME}/.local/share/applications"

echo "Removing Desktop Pet..."
rm -rf "${INSTALL_PREFIX}"
rm -f "${BIN_DIR}/desktop-pet"
rm -f "${APPS_DIR}/desktop-pet.desktop"
rm -f "${AUTOSTART_DIR}/desktop-pet.desktop"

echo "Desktop Pet uninstalled successfully."
