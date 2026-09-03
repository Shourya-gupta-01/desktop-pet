# 🗡️ Desktop Pet — Multimodal AI Companion (Zoro Edition)

[![Rust](https://img.shields.io/badge/Rust-1.75%2B-orange?logo=rust)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-green)](https://github.com/Shourya-gupta-01/desktop-pet)
[![ZeroMQ](https://img.shields.io/badge/IPC-ZeroMQ%20%2B%20Protobuf-red)](https://zeromq.org/)
[![AI Backend](https://img.shields.io/badge/AI-Ollama%20(Qwen2.5--VL)%20%7C%20Gemini%202.0-purple)](https://ollama.com/)

**Desktop Pet** is a lightweight, low-latency, multimodal desktop companion powered by a high-performance **Rust UI Shell** and an extensible **Python AI Brain**. Featuring **Zoro** chibi sprites with transparent overlays, global Push-to-Talk voice interaction, 720p screen reading, webcam perception, ambient face presence detection, and full native OS automation across **Linux (Wayland & X11)** and **Windows 10/11**.

---

## 🌟 Key Features

- 🎙️ **Unified Push-to-Talk Voice AI (`Super + Z` / `Win + Z`)**:
  - Hold `Super + Z` (or `Win + Z`), speak your question or command, and release to execute.
  - Sub-second local speech-to-text powered by **Faster-Whisper** and **Silero VAD**.
  - Serious, hyper-concise, direct single-line/single-word responses with zero fluff.
- 👏 **Double-Clap Acoustic Wakeup**:
  - Clap twice to wake the pet up and start listening without touching the keyboard.
- 🖥️ **720p Dual Vision AI**:
  - **Screen Vision**: Ask *"What is on my screen?"* or *"Read this error/code"* — captures the screen at 720p in volatile RAM and analyzes it.
  - **Webcam Vision**: Ask *"Look at me"* or *"What am I holding?"* — takes a snapshot via webcam and describes it.
- ⚡ **1-Click Hybrid AI Switching (Local 💻 <-> Cloud 🚀)**:
  - Toggle seamlessly between offline local models (**Ollama Qwen2.5-VL 7B**) and cloud speed (**Google Gemini 2.0 Flash**).
  - Switch anytime via voice command (*"Switch to Gemini"* / *"Switch to local"*) or the `toggle_ai.sh` script.
- 🚀 **Native OS Automation & Navigation**:
  - Launch 160+ applications (*"Open Spotify"*, *"Launch file manager"*, *"Open Discord"*).
  - Execute terminal commands (*"Run cargo check"*, *"In terminal run htop"*).
  - Compound web searches (*"Open youtube.com and search for lofi hip hop"*).
  - Real-time hardware telemetry (*"Tell my RAM and disk usage"*, *"Check battery"*).
- 👤 **Ambient Face Presence Awareness**:
  - Built-in **YuNet ONNX** face detector periodically checks user presence, greeting you when you return.
- 🛡️ **Rust Process Supervisor**:
  - The Rust shell automatically discovers, launches, and monitors the Python Brain sidecar, automatically recovering and restarting it if it crashes.
- 🪟 **Frosted-Glass UI**:
  - Translucent speech bubbles (~50% opacity) and tinted character sprites designed for high visibility over code and dark backgrounds.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Desktop Pet Architecture                        │
├───────────────────────────────┬────────────────────────────────────────┤
│           pet-shell           │               pet-brain                │
│    (Native Rust Binary)       │          (Python AI Sidecar)           │
│  - egui/Wayland UI            │  - Faster-Whisper + Silero VAD         │
│  - Audio & Global Hotkeys     │  - Dual Vision & Multi-Backend AI      │
│  - ZeroMQ SUB/PUSH Client     │  - ZeroMQ PUB/PULL Server              │
│  - Process Supervisor ───────►│  - Plugin System & OS Navigation       │
│    (Spawns & Monitors Brain)  │                                        │
└───────────────────────────────┴────────────────────────────────────────┘
```

---

## 📥 Installation Guide

### Option 1: Linux (Arch, Ubuntu, Fedora, Debian, etc.)

#### 1. Clone the repository
```bash
git clone https://github.com/Shourya-gupta-01/desktop-pet.git
cd desktop-pet
```

#### 2. Build and Install
```bash
# Build the release distribution bundle
./packaging/build_dist.sh

# Run the automated installer
./dist/desktop-pet/install.sh
```

The installer will:
- Verify system dependencies (`grim`, `slurp`, `playerctl`, `python3`).
- Verify **Ollama** and check for the `qwen2.5vl:7b` vision model (prompts `ollama pull` if missing).
- Set up an isolated Python virtual environment in `~/.local/share/desktop-pet/pet-brain/.venv`.
- Create a launcher command in `~/.local/bin/desktop-pet`.
- Register XDG Application Menu (`desktop-pet.desktop`) and Autostart on login (`~/.config/autostart/`).

---

### Option 2: Windows 10/11

#### 1. Clone the repository in PowerShell
```powershell
git clone https://github.com/Shourya-gupta-01/desktop-pet.git
cd desktop-pet
```

#### 2. Run the Windows Installer
```powershell
# Run the PowerShell installer
powershell -ExecutionPolicy Bypass -File .\packaging\installer\install.ps1
```

The installer will:
- Check Python 3 and Ollama.
- Deploy files to `$env:LOCALAPPDATA\desktop-pet`.
- Create a `.venv` and install all dependencies.
- Create a **Desktop Shortcut** (`Desktop Pet.lnk`) with the Zoro icon.
- Add the shortcut to **Windows Startup (`shell:startup`)** for automatic login execution.

---

## 🚀 Usage & Controls

### ⌨️ Hotkeys & Gestures
| Trigger | Action | Platform |
| :--- | :--- | :--- |
| **`Super + Z` (Hold & Speak)** | Push-to-Talk Voice AI | Linux (Hyprland/Sway/X11) |
| **`Win + Z` (Hold & Speak)** | Push-to-Talk Voice AI | Windows (`hotkey_helper.ps1`) |
| **Double-Clap** | Hands-free audio wake-up | Linux & Windows |
| **`./toggle_ai.sh`** | 1-Click Toggle between Local AI & Gemini | Linux & Windows |

---

### 🗣️ Example Voice Commands

#### 🤖 General AI & Math (Concise 1-Line Responses)
- *"What is the capital of Japan?"* $
ightarrow$ `Tokyo.`
- *"What is 128 times 16?"* $
ightarrow$ `2048.`
- *"Who wrote One Piece?"* $
ightarrow$ `Eiichiro Oda.`

#### 🖥️ Screen & Webcam Vision
- *"What is on my screen?"* $
ightarrow$ Describes active window, code, or error.
- *"Explain this error on my screen."* $
ightarrow$ Analyzes the visible traceback.
- *"Look at me."* $
ightarrow$ Describes what is in front of the webcam.

#### 🚀 Native Application Launching
- *"Open Spotify"* $
ightarrow$ Launches Spotify.
- *"Open Discord"* $
ightarrow$ Launches Discord.
- *"Open file manager"* $
ightarrow$ Opens Dolphin / Explorer.
- *"Open terminal"* $
ightarrow$ Opens Kitty / Windows Terminal.

#### 💻 Terminal Commands
- *"Run cargo check"* $
ightarrow$ Spawns terminal and runs `cargo check`.
- *"Run git status"* $
ightarrow$ Runs `git status`.
- *"In terminal run htop"* $
ightarrow$ Opens process monitor.

#### 🌐 Web & Media Control
- *"Open youtube.com and search for lofi beats"*
- *"Open github.com and search for whisper"*
- *"Pause music"* / *"Resume music"* / *"Skip song"*
- *"Volume up"* / *"Volume down"* / *"Mute"*

#### 💾 Hardware Telemetry
- *"Tell my RAM and disk usage"* $
ightarrow$ `RAM: 34.2% (10.8/31.2 GB) | Disk: 23.0% (297.2 GB free) | CPU: 12% 🚀`
- *"Check battery"* $
ightarrow$ `Battery: 85% (⚡ Charging)! ✨`
- *"Lock screen"* $
ightarrow$ Locks desktop session.

#### ⚡ AI Backend Switching
- *"Switch to Gemini"* $
ightarrow$ Switches to Google Gemini 2.0 Flash cloud backend.
- *"Switch to local"* $
ightarrow$ Switches to Ollama Qwen2.5-VL offline backend.

---

## ⚙️ Configuration & Environment Variables

To configure optional API keys (such as Google Gemini), create or edit `pet-brain/.env` (see [`pet-brain/.env.example`](file:///pet-brain/.env.example)):

```bash
# Copy template
cp pet-brain/.env.example pet-brain/.env
```

```env
# AI Backend Configuration
# Options: "local" (Ollama) or "gemini" (Google Gemini)
AI_BACKEND=local

# Local Ollama Settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5vl:7b

# Google Gemini API Key (Required only if using Gemini)
# Get a free key at: https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

---

## 🪟 Recommended Hyprland Configuration (Linux)

Add this snippet to `~/.config/hypr/hyprland.conf` for transparent floating overlay and hotkey binding:

```ini
# Desktop Pet Window Rules
windowrulev2 = float, class:^(desktop-pet)$
windowrulev2 = noborder, class:^(desktop-pet)$
windowrulev2 = pin, class:^(desktop-pet)$
windowrulev2 = noinitialfocus, class:^(desktop-pet)$
windowrulev2 = size 620 230, class:^(desktop-pet)$
windowrulev2 = move 100%-635 100%-245, class:^(desktop-pet)$

# Push-to-Talk (Hold Super+Z to talk, Release to execute)
bind = SUPER, Z, exec, echo "voice_press" | socat - UDP-DATAGRAM:127.0.0.1:5556
bindr = SUPER, Z, exec, echo "voice_release" | socat - UDP-DATAGRAM:127.0.0.1:5556
```

---

---

## 🔌 Creating Custom Plugins

Desktop Pet is designed with a plug-and-play modular architecture. You can easily add new capabilities, sensors, integrations, or behaviors by dropping a Python folder into `pet-brain/plugins/`.

### Quick Example (`pet-brain/plugins/reminder/plugin.py`):
```python
from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent
import datetime

class ReminderPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="ReminderPlugin",
            version="1.0.0",
            description="Hourly posture and hydration reminders.",
            tick_interval=3600.0, # Run every 1 hour
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context

    def on_tick(self, dt: float) -> None:
        self.ctx.send_speech("Time to stretch and drink water! 💧✨")
        self.ctx.send_emotion("happy", priority=120, duration=5.0)
```

👉 **For the complete developer guide, API reference, and event list, check the [Plugin Development Guide](docs/PLUGIN_GUIDE.md).**

## 🛠️ Development & Manual Execution

To run the project from source during development:

```bash
# Terminal 1: Run Python AI Brain
cd pet-brain
python main.py

# Terminal 2: Run Rust UI Shell
cd pet-shell
cargo run
```

### Running Test Suites
```bash
cd pet-brain
python test_loader.py
python test_os_nav_plugin.py
python test_stt_plugin.py
python test_ai_switching.py
```

---

## 📄 License
This project is open-source under the MIT License.
