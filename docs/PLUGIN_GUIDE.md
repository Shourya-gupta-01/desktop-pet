# 🔌 Desktop Pet — Plugin Development Guide

Desktop Pet features a modular, dynamic plugin system. Any folder placed inside `pet-brain/plugins/` containing a `plugin.py` (and optional `manifest.yaml`) is automatically discovered, validated, and loaded into the AI Brain event loop without modifying core engine code.

---

## 📁 1. Plugin Directory Structure

Every plugin lives in its own subdirectory inside `pet-brain/plugins/`:

```
pet-brain/plugins/my_custom_plugin/
├── manifest.yaml       # (Optional) Static metadata and subscriptions
└── plugin.py           # (Required) Plugin class inheriting from BasePlugin
```

---

## 🚀 2. Quickstart: Building a Plugin in 3 Steps

### Step 1: Create the Plugin Folder
```bash
mkdir -p pet-brain/plugins/my_custom_plugin
```

### Step 2: Define `plugin.py`
Create `pet-brain/plugins/my_custom_plugin/plugin.py`:

```python
from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent
import datetime

class MyCustomPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="MyCustomPlugin",
            version="1.0.0",
            author="Your Name",
            description="Example plugin demonstrating periodic ticks and custom events.",
            # Subscribed events: ["hotkey:voice_action_z", "audio_event", "custom_event", "*"]
            subscriptions=["hotkey:my_custom_hotkey"],
            # Polling hook: run on_tick() every 60 seconds (set None to disable)
            tick_interval=60.0,
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.ctx.logger.info("MyCustomPlugin loaded successfully!")

    def on_tick(self, dt: float) -> None:
        """Runs periodically based on manifest.tick_interval."""
        now_str = datetime.datetime.now().strftime("%I:%M %p")
        # Send a speech bubble and emotion to the desktop pet
        self.ctx.send_speech(f"Ding! The time is {now_str} ⏰")
        self.ctx.send_emotion("happy", priority=120, duration=4.0)

    def on_event(self, event: IncomingEvent) -> None:
        """Runs whenever a subscribed event is triggered."""
        if event.hotkey_id == "my_custom_hotkey":
            self.ctx.logger.info("Custom hotkey triggered!")
            self.ctx.send_speech("Custom action executed! 🚀")
            self.ctx.send_emotion("proud", priority=150, duration=5.0)

    def on_unload(self) -> None:
        self.ctx.logger.info("MyCustomPlugin unloaded cleanly.")
```

### Step 3: Test Your Plugin
Restart `pet-brain/main.py` or run `python pet-brain/test_loader.py` to verify discovery:
```bash
python pet-brain/test_loader.py
```

---

## 🛠️ 3. Plugin API Reference

### `PluginContext` Methods

When your plugin loads, `on_load(context)` receives a `PluginContext` instance:

| Method | Parameters | Description |
| :--- | :--- | :--- |
| `self.ctx.send_speech(text, is_streaming=False)` | `text: str`, `is_streaming: bool` | Displays a speech bubble above the pet. |
| `self.ctx.send_emotion(emotion_id, priority, duration)` | `emotion_id: str`, `priority: int` (0-255), `duration: float` (seconds) | Changes the pet sprite and emotion with priority arbitration. |
| `self.ctx.ai.generate_response(prompt, image_bytes, stream_callback)` | `prompt: str`, `image_bytes: bytes`, `callback` | Generates a response from the active AI (Ollama or Gemini). |
| `self.ctx.stt.transcribe(audio_buffer)` | `audio_buffer: np.ndarray` | Transcribes raw PCM audio buffer to text via Faster-Whisper. |
| `self.ctx.logger.info(msg)` | `msg: str` | Scoped logging with plugin name prefix. |

---

## 🎭 4. Available Emotion Identifiers

The Desktop Pet supports **16 emotion states** (each mapped to transparent Zoro chibi sprites):

| Emotion ID | Sprite Mood | Recommended Use Cases |
| :--- | :--- | :--- |
| `idle` | Calm / Neutral | Default resting state |
| `happy` | Cheerful / Smiling | Success, completion, compliments |
| `curious` | Inquisitive / Alert | Listening to user speech, processing questions |
| `proud` | Confident / Smug | Reporting stats, executing system tasks |
| `angry` | Annoyed / Fierce | Errors, failed commands |
| `startled` | Shocked / Surprised | Low battery alerts, loud noise, claps |
| `sleepy` | Drowsy | Inactive for long periods |
| `bored` | Yawning | Long periods of idle |
| `eating` | Munching | Relaxed ambient states |
| `dizzy` | Swirling | Intensive processing / errors |
| `reading` | Focused | Reading screen code or analyzing images |

---

## 📡 5. Event Subscriptions

In `get_manifest().subscriptions`, you can subscribe to:

- `"hotkey:voice_action_z"`: Push-to-Talk activation.
- `"audio_event"`: Audio sensor events (including double-claps).
- `"hotkey:os_action"`: System action hotkey.
- `"custom_event_name"`: Any custom string sent over IPC.
- `"*"`: Wildcard subscription to receive all broadcast events.
