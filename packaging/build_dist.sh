#!/usr/bin/env bash
set -e

# Colors
GREEN="\\033[0;32m"
BLUE="\\033[0;34m"
YELLOW="\\033[1;33m"
NC="\\033[0m"

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}       Building Desktop Pet Standalone Distribution  ${NC}"
echo -e "${BLUE}=====================================================${NC}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist/desktop-pet"

# 1. Compile pet-shell in release mode
echo -e "${YELLOW}[1/4] Compiling pet-shell (release mode)...${NC}"
cd "${ROOT_DIR}/pet-shell"
cargo build --release

# 2. Clean & prepare dist directory
echo -e "${YELLOW}[2/4] Assembling distribution structure in ${DIST_DIR}...${NC}"
rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}/bin"
mkdir -p "${DIST_DIR}/assets/sprites"
mkdir -p "${DIST_DIR}/pet-brain"

# 3. Copy Binaries & Assets
echo -e "${YELLOW}[3/4] Copying binaries, sprites, and brain modules...${NC}"
cp "${ROOT_DIR}/pet-shell/target/release/pet-shell" "${DIST_DIR}/bin/pet-shell"
chmod +x "${DIST_DIR}/bin/pet-shell"

# Copy Assets
cp -r "${ROOT_DIR}/assets/sprites/"* "${DIST_DIR}/assets/sprites/"

# Copy Brain Modules
cp -r "${ROOT_DIR}/pet-brain/core" "${DIST_DIR}/pet-brain/"
cp -r "${ROOT_DIR}/pet-brain/plugins" "${DIST_DIR}/pet-brain/"
cp -r "${ROOT_DIR}/pet-brain/scripts" "${DIST_DIR}/pet-brain/"
cp "${ROOT_DIR}/pet-brain/main.py" "${DIST_DIR}/pet-brain/"
cp "${ROOT_DIR}/pet-brain/pet_pb2.py" "${DIST_DIR}/pet-brain/"
cp "${ROOT_DIR}/pet-brain/requirements.txt" "${DIST_DIR}/pet-brain/"
cp "${ROOT_DIR}/pet-brain/.env.example" "${DIST_DIR}/pet-brain/"
if [ -f "${ROOT_DIR}/toggle_ai.sh" ]; then
    cp "${ROOT_DIR}/toggle_ai.sh" "${DIST_DIR}/bin/"
    chmod +x "${DIST_DIR}/bin/toggle_ai.sh"
fi

# 4. Copy Installer & Uninstaller (Linux & Windows)
echo -e "${YELLOW}[4/4] Generating installer and packaging scripts for Linux and Windows...${NC}"
cp "${ROOT_DIR}/packaging/installer/install.sh" "${DIST_DIR}/install.sh"
cp "${ROOT_DIR}/packaging/installer/uninstall.sh" "${DIST_DIR}/uninstall.sh"
cp "${ROOT_DIR}/packaging/installer/install.ps1" "${DIST_DIR}/install.ps1"
cp "${ROOT_DIR}/packaging/installer/uninstall.ps1" "${DIST_DIR}/uninstall.ps1"
cp "${ROOT_DIR}/packaging/installer/hotkey_helper.ps1" "${DIST_DIR}/hotkey_helper.ps1"
chmod +x "${DIST_DIR}/install.sh" "${DIST_DIR}/uninstall.sh"

echo -e "${GREEN}=====================================================${NC}"
echo -e "${GREEN} [SUCCESS] Standalone distribution ready in:        ${NC}"
echo -e "${GREEN}           ${DIST_DIR}                              ${NC}"
echo -e "${GREEN} Run ./install.sh inside the dist folder to install! ${NC}"
echo -e "${GREEN}=====================================================${NC}"
