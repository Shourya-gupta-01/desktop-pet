# AI Desktop Pet — Features & File Structure

## Overview

A modular, locally hosted AI desktop pet (Shimeji-style virtual assistant) with a transparent, always-on-top chibi GUI. Runs fully offline via Ollama, cross-platform on Windows and Linux, with a plugin architecture so new AI features can be added without touching core code.

**Architecture:** hybrid two-process design — a compiled **Rust shell** handles everything latency-critical (rendering, input, audio, screen capture), and a **Python backend** handles all AI logic and plugins, communicating over a low-latency IPC channel.

---

## Features

### Core Experience
- Transparent, frameless, always-on-top desktop overlay (chibi sprite)
- Click-through rendering — doesn't block interaction with the desktop underneath
- Pixel-font speech bubbles for text output
- 16 dynamic emotion states with an animated transition system (priority-based, so higher-priority reactions like "startled" can interrupt lower-priority ones like "idle")
- Cross-platform: native support for Windows and Linux out of the box

### Input & Interaction
- Global, non-privileged hotkeys (work even when another app has focus)
- Ambient audio detection — clap/amplitude-based triggers
- Offline speech-to-text (STT) for voice interaction
- Screen-aware context — the pet can "see" and reason about what's on screen

### AI Capabilities (strictly local, zero API cost, full privacy)
- Text reasoning/chat via a local LLM (Mistral or Llama3 through Ollama)
- Vision-based screen Q&A via LLaVA through Ollama
- Voice chat: STT → local LLM → spoken/text response
- Clap/amplitude-triggered emotional reactions
- Real-time face verification via a custom Siamese Neural Network pipeline (exported to ONNX for fast inference)
- OS navigation / command execution as a first-class plugin (open apps, run system commands, etc.)

### Plugin System (the extensibility backbone)
- Fully plugin-agnostic core — the main loop and loader know nothing about individual features
- Auto-discovery: drop a new plugin folder into `plugins/`, restart, it's active — no core code changes
- Every plugin implements a standard `base_plugin.py` contract (`on_load`, `on_event`, `on_tick`, `on_unload`, `get_manifest`)
- Per-plugin `manifest.yaml` declaring required capabilities (camera, shell access, filesystem, network) for auditability and safe gating
- Event-bus/IPC-mediated communication — plugins never reach into the GUI or shell directly
- New AI features are added purely in Python, with zero changes required to the Rust shell

### Performance & Latency
- Rust-native shell for rendering, hotkeys, audio, and screen capture — sub-frame latency, no GIL/interpreter overhead on the interactive path
- Persistent binary IPC (ZeroMQ + Protobuf) between shell and AI backend — single-digit-millisecond round trip, no HTTP/JSON overhead
- Threaded/async AI calls (`ai_bridge.py`) so a slow model response never blocks input handling or animation
- Streamed LLM responses (token-by-token) so speech bubbles update incrementally instead of waiting on full generation
- Event-triggered (not polled) screen capture and vision calls to avoid wasted CPU/GPU cycles

### Deployment
- Ollama startup health-check (service running, required models pulled) with user-facing error messaging
- Native packaging: Rust shell compiles to a single binary per OS; Python backend packaged as a PyInstaller sidecar binary launched and monitored by the shell
- Autostart registration: Windows `.lnk` shortcuts, Linux `.desktop` files in `~/.config/autostart`
- Single installer handles dependency setup, binary builds, and autostart configuration

---

## File Structure

```
desktop-pet/
├── proto/
│   └── pet.proto                     # shared IPC message contract (InputEvent, EmotionCommand, etc.)
│
├── pet-shell/                        # Rust — latency-critical native shell
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── window.rs                 # transparent/frameless/click-through render
│       ├── sprite_renderer.rs
│       ├── input/
│       │   ├── hotkeys.rs
│       │   └── audio.rs              # clap/amplitude detection
│       ├── capture/
│       │   └── screen.rs             # screen capture, fires on IPC request only
│       └── ipc/
│           ├── client.rs
│           └── pet.pb.rs             # generated from pet.proto
│
├── pet-brain/                        # Python — all AI logic + plugin system
│   ├── requirements.txt
│   ├── main.py
│   ├── core/
│   │   ├── ipc_server.py             # ZeroMQ + protobuf (de)serialization
│   │   ├── base_plugin.py            # abstract plugin contract
│   │   ├── plugin_loader.py          # discovery, validation, lifecycle, dispatch
│   │   ├── ai_bridge.py              # async/threaded Ollama access
│   │   ├── emotion_engine.py         # 16-emotion state machine + transition priority
│   │   ├── stt_engine.py             # faster-whisper wrapper
│   │   └── pet_pb2.py                # generated from pet.proto
│   ├── plugins/
│   │   ├── os_navigation/
│   │   │   ├── plugin.py
│   │   │   └── manifest.yaml
│   │   ├── voice_chat/
│   │   │   ├── plugin.py
│   │   │   └── manifest.yaml
│   │   ├── vision_chat/
│   │   │   ├── plugin.py
│   │   │   └── manifest.yaml
│   │   ├── clap_reaction/
│   │   │   ├── plugin.py
│   │   │   └── manifest.yaml
│   │   └── face_verify/
│   │       ├── plugin.py
│   │       ├── model/
│   │       │   └── siamese.onnx
│   │       └── manifest.yaml
│   └── docs/
│       └── plugin_contract.md        # documents the base_plugin.py API surface
│
├── config/
│   ├── default_config.yaml           # model names, hotkeys, capture interval
│   └── user_config.yaml              # generated on first run, gitignored
│
├── assets/
│   ├── sprites/
│   │   ├── idle/
│   │   ├── happy/
│   │   ├── sad/
│   │   ├── curious/
│   │   ├── startled/
│   │   └── ...                       # one folder per emotion (16 total)
│   ├── fonts/
│   │   └── pixel_font.ttf
│   └── icons/
│       └── tray_icon.png
│
├── packaging/
│   ├── pyinstaller.spec              # for the pet-brain sidecar binary
│   ├── windows/
│   │   └── create_shortcut.py        # .lnk generation
│   ├── linux/
│   │   └── autostart.desktop.template
│   └── installer/                    # cross-platform installer (Go or scripts)
│
├── scratch/                          # throwaway environment-proof scripts
│   ├── rust/
│   ├── python/
│   └── ipc_test/
│
└── tests/
    ├── rust/
    └── python/
```
