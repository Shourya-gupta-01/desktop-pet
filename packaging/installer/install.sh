#!/usr/bin/env bash
set -e

# ==============================================================================
# Desktop Pet Automated Native Installer (Linux / Wayland / Hyprland)
# ==============================================================================

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
BOLD="\033[1m"
NC="\033[0m"

INSTALL_PREFIX="${HOME}/.local/share/desktop-pet"
BIN_DIR="${HOME}/.local/bin"
AUTOSTART_DIR="${HOME}/.config/autostart"
APPS_DIR="${HOME}/.local/share/applications"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}${BOLD}"
echo "    ____            __    __               ____       __  "
echo "   / __ \\___  _____/ /__/ /_____  ____    / __ \\___  / /_ "
echo "  / / / / _ \\/ ___/ //_/ __/ __ \\/ __ \\  / /_/ / _ \\/ __/ "
echo " / /_/ /  __(__  ) ,< / /_/ /_/ / /_/ / / ____/  __/ /_   "
echo "/_____/\\___/____/_/|_|\\__/\\____/ .___/ /_/    \\___/\\__/   "
echo "                              /_/                         "
echo -e "${NC}"
echo -e "${BLUE}>>> Starting Desktop Pet Automated Installation...${NC}\n"

# 1. Check System Dependencies
echo -e "${YELLOW}[1/6] Checking system tools & utilities...${NC}"
MISSING_DEPS=()

for tool in grim slurp playerctl python3; do
    if ! command -v "$tool" &>/dev/null; then
        MISSING_DEPS+=("$tool")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Notice: The following recommended utilities were not found: ${MISSING_DEPS[*]}${NC}"
    echo -e "Install them via package manager if needed (e.g. sudo pacman -S grim slurp playerctl)"
fi

# 2. Check Ollama & AI Models
echo -e "${YELLOW}[2/6] Verifying Ollama AI engine...${NC}"
if command -v ollama &>/dev/null; then
    echo -e "${GREEN}  ✓ Ollama CLI is installed.${NC}"
    if ollama list 2>/dev/null | grep -q "qwen2.5vl:7b"; then
        echo -e "${GREEN}  ✓ Vision AI model (qwen2.5vl:7b) is already downloaded.${NC}"
    else
        echo -e "${YELLOW}  ! Model qwen2.5vl:7b not yet downloaded. Run: ollama pull qwen2.5vl:7b${NC}"
    fi
else
    echo -e "${YELLOW}  ! Ollama CLI not detected. (You can still use Google Gemini API in .env)${NC}"
fi

# 3. Create target directories
echo -e "${YELLOW}[3/6] Setting up installation directories in ${INSTALL_PREFIX}...${NC}"
mkdir -p "${INSTALL_PREFIX}/bin"
mkdir -p "${INSTALL_PREFIX}/assets/sprites"
mkdir -p "${INSTALL_PREFIX}/pet-brain"
mkdir -p "${BIN_DIR}"
mkdir -p "${AUTOSTART_DIR}"
mkdir -p "${APPS_DIR}"

# 4. Copy Binaries & Assets
echo -e "${YELLOW}[4/6] Copying binaries, assets, and AI modules...${NC}"
if [ -d "${SCRIPT_DIR}/bin" ]; then
    cp -r "${SCRIPT_DIR}/bin/"* "${INSTALL_PREFIX}/bin/"
    cp -r "${SCRIPT_DIR}/assets/sprites/"* "${INSTALL_PREFIX}/assets/sprites/"
    cp -r "${SCRIPT_DIR}/pet-brain/"* "${INSTALL_PREFIX}/pet-brain/"
else
    cp "${SCRIPT_DIR}/../../pet-shell/target/release/pet-shell" "${INSTALL_PREFIX}/bin/pet-shell" 2>/dev/null || \
    cp "${SCRIPT_DIR}/../pet-shell/target/release/pet-shell" "${INSTALL_PREFIX}/bin/pet-shell" 2>/dev/null || true
    cp -r "${SCRIPT_DIR}/../../assets/sprites/"* "${INSTALL_PREFIX}/assets/sprites/" 2>/dev/null || \
    cp -r "${SCRIPT_DIR}/../assets/sprites/"* "${INSTALL_PREFIX}/assets/sprites/" 2>/dev/null || true
    cp -r "${SCRIPT_DIR}/../../pet-brain/core" "${INSTALL_PREFIX}/pet-brain/" 2>/dev/null || true
    cp -r "${SCRIPT_DIR}/../../pet-brain/plugins" "${INSTALL_PREFIX}/pet-brain/" 2>/dev/null || true
    cp -r "${SCRIPT_DIR}/../../pet-brain/scripts" "${INSTALL_PREFIX}/pet-brain/" 2>/dev/null || true
    cp "${SCRIPT_DIR}/../../pet-brain/main.py" "${INSTALL_PREFIX}/pet-brain/" 2>/dev/null || true
    cp "${SCRIPT_DIR}/../../pet-brain/pet_pb2.py" "${INSTALL_PREFIX}/pet-brain/" 2>/dev/null || true
    cp "${SCRIPT_DIR}/../../pet-brain/requirements.txt" "${INSTALL_PREFIX}/pet-brain/" 2>/dev/null || true
    cp "${SCRIPT_DIR}/../../pet-brain/.env.example" "${INSTALL_PREFIX}/pet-brain/" 2>/dev/null || true
fi
chmod +x "${INSTALL_PREFIX}/bin/"* 2>/dev/null || true

# 5. Setup Python Venv
echo -e "${YELLOW}[5/6] Setting up Python dependencies...${NC}"
cd "${INSTALL_PREFIX}/pet-brain"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv 2>/dev/null || true
fi
if [ -f ".venv/bin/pip" ]; then
    .venv/bin/pip install --upgrade pip -q 2>/dev/null || true
    .venv/bin/pip install -r requirements.txt -q 2>/dev/null || true
fi

# Create launcher script in ~/.local/bin/desktop-pet
echo "#!/usr/bin/env bash" > "${BIN_DIR}/desktop-pet"
echo "export DESKTOP_PET_ASSETS_DIR=\"${INSTALL_PREFIX}/assets/sprites\"" >> "${BIN_DIR}/desktop-pet"
echo "export DESKTOP_PET_BRAIN_BIN=\"${INSTALL_PREFIX}/pet-brain/.venv/bin/python ${INSTALL_PREFIX}/pet-brain/main.py\"" >> "${BIN_DIR}/desktop-pet"
echo "exec \"${INSTALL_PREFIX}/bin/pet-shell\" \"\$@\"" >> "${BIN_DIR}/desktop-pet"
chmod +x "${BIN_DIR}/desktop-pet"

# 6. Register Desktop Entry & Autostart
echo -e "${YELLOW}[6/6] Registering XDG Desktop Entry & Autostart...${NC}"
echo "[Desktop Entry]" > "${APPS_DIR}/desktop-pet.desktop"
echo "Name=Desktop Pet" >> "${APPS_DIR}/desktop-pet.desktop"
echo "Comment=Interactive Multimodal Desktop AI Companion" >> "${APPS_DIR}/desktop-pet.desktop"
echo "Exec=${BIN_DIR}/desktop-pet" >> "${APPS_DIR}/desktop-pet.desktop"
echo "Icon=${INSTALL_PREFIX}/assets/sprites/idle/placeholder.png" >> "${APPS_DIR}/desktop-pet.desktop"
echo "Terminal=false" >> "${APPS_DIR}/desktop-pet.desktop"
echo "Type=Application" >> "${APPS_DIR}/desktop-pet.desktop"
echo "Categories=Utility;AI;" >> "${APPS_DIR}/desktop-pet.desktop"
echo "StartupWMClass=desktop-pet" >> "${APPS_DIR}/desktop-pet.desktop"

cp "${APPS_DIR}/desktop-pet.desktop" "${AUTOSTART_DIR}/desktop-pet.desktop"

echo -e "\n${GREEN}${BOLD}==============================================================================${NC}"
echo -e "${GREEN}${BOLD}       🎉 Desktop Pet Installation Completed Successfully!                     ${NC}"
echo -e "${GREEN}${BOLD}==============================================================================${NC}"
echo -e "\n${BOLD}Installed to:${NC}"
echo -e "  • Binary & Assets : ${INSTALL_PREFIX}"
echo -e "  • Launcher        : ${BIN_DIR}/desktop-pet"
echo -e "  • Autostart Entry : ${AUTOSTART_DIR}/desktop-pet.desktop"
echo -e "  • App Menu Entry  : ${APPS_DIR}/desktop-pet.desktop\n"
echo -e "${CYAN}Launch anytime with: ${BOLD}desktop-pet${NC}\n"
