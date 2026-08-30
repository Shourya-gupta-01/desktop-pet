# Desktop Pet — Plugin API Contract

## Overview

The Desktop Pet architecture is built around a **pluggable, event-driven AI core**. All custom behaviors, AI features, and user automations are implemented as isolated plugins in `pet-brain/plugins/` without modifying the core event loop or the Rust UI shell.

Every plugin inherits from `BasePlugin` and interacts with the pet through the `PluginContext`.

---

## 1. Plugin Lifecycle

The plugin lifecycle is managed by `PluginLoader`:

```
┌────────────────────────────────────────────────────────┐
│ 1. Discovery    : Scans plugins/ directory             │
│ 2. Validation   : Verifies BasePlugin & Manifest       │
│ 3. on_load()    : Injects PluginContext, init state    │
│ 4. Execution    : Dispatches on_event() & on_tick()    │
│ 5. on_unload()  : Cleanup on shutdown or reload        │
└────────────────────────────────────────────────────────┘
```

1. **Discovery**: On startup, `pet-brain` scans `pet-brain/plugins/` for plugin directories containing an `__init__.py` or `plugin.py`.
2. **Registration**: The loader reads `get_manifest()` to register event subscriptions and ticking intervals.
3. **Initialization (`on_load`)**: Called once with a populated `PluginContext`. Plugins initialize resources, load models, or restore local state.
4. **Event Handling (`on_event`)**: Called whenever an event matches the plugin's declared `subscriptions`.
5. **Periodic Execution (`on_tick`)**: Optional polling hook executed every `tick_interval` seconds if declared in the manifest.
6. **Teardown (`on_unload`)**: Invoked during brain shutdown or hot-reloading to release sockets, threads, and files.

---

## 2. Core Class Definitions

Defined in `pet-brain/core/base_plugin.py`.

### `BasePlugin`

The abstract base class every plugin must inherit from:

```python
from abc import ABC, abstractmethod
from core.base_plugin import PluginManifest, PluginContext, IncomingEvent

class BasePlugin(ABC):
    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """Declare plugin metadata, event subscriptions, and capabilities."""
        pass

    def on_load(self, context: PluginContext) -> None:
        """Called once when plugin is initialized."""
        pass

    def on_event(self, event: IncomingEvent) -> None:
        """Called when a subscribed event (hotkey, audio, screen) occurs."""
        pass

    def on_tick(self, dt: float) -> None:
        """Called periodically if manifest.tick_interval is set."""
        pass

    def on_unload(self) -> None:
        """Called during shutdown for cleanup."""
        pass
```

---

### `PluginManifest`

Defines the capabilities, subscriptions, and identity of the plugin:

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Unique human-readable name of the plugin. |
| `version` | `str` | Semantic version string (e.g. `"1.0.0"`). |
| `author` | `str` | Plugin author name or handle. |
| `description` | `str` | Summary of what the plugin does. |
| `subscriptions` | `List[str]` | Event types to listen for (e.g. `["input_event", "audio_event", "screen_frame"]`). Can also match specific hotkeys like `"hotkey:global_action_x"` or all events with `"*"` |
| `tick_interval` | `Optional[float]` | Tick frequency in seconds (e.g. `1.0`, `5.0`). `None` if `on_tick` is not used. |
| `required_capabilities` | `List[str]` | Declared capability requirements (e.g. `["ollama", "vision", "microphone"]`). |

---

### `PluginContext`

The gateway provided to plugins to interact with the environment:

| Method / Property | Type | Description |
| :--- | :--- | :--- |
| `send_emotion(emotion_id, priority)` | `Method` | Requests the Rust shell to swap sprite to `emotion_id` (e.g. `"happy"`, `"startled"`, `"curious"`, `"idle"`). |
| `send_speech(text, is_streaming)` | `Method` | Displays a speech bubble over the pet. Set `is_streaming=True` for token-by-token streaming. |
| `send_raw_message(message)` | `Method` | Sends arbitrary raw Protobuf `PetMessage` to the Rust shell over ZeroMQ IPC. |
| `ai` | `Optional[AIBridge]` | Access to local Ollama inference (`prompt()`, `prompt_vision()`, `stream()`). |
| `config` | `Dict[str, Any]` | Read-only access to user configuration settings. |
| `logger` | `logging.Logger` | Scoped logger instance for structured output. |
| `state` | `Dict[str, Any]` | Runtime key-value storage for the plugin. |

---

### `IncomingEvent`

Normalized event wrapper passed to `on_event(event)`:

| Property | Type | Description |
| :--- | :--- | :--- |
| `event_type` | `str` | Name of the event (`"input_event"`, `"audio_event"`, `"screen_frame"`, `"custom"`). |
| `data` | `Dict[str, Any]` | Dictionary of parsed event parameters. |
| `timestamp` | `float` | Unix timestamp of when the event was generated. |
| `is_hotkey` | `bool` | Helper: `True` if event is an `input_event`. |
| `hotkey_id` | `Optional[str]` | The hotkey identifier string (e.g. `"global_action_x"`). |
| `is_audio` | `bool` | Helper: `True` if event is an `audio_event`. |
| `is_clap` | `bool` | Helper: `True` if audio event was confirmed as an acoustic clap. |
| `raw_message` | `PetMessage` | The underlying raw Protobuf message received from IPC. |

---

## 3. Example Plugin Implementations

### Example 1: Audio Reaction Plugin (`clap_reaction.py`)

A reactive plugin that makes the pet react to claps and loud noises:

```python
from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent

class ClapReactionPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="ClapReaction",
            version="1.0.0",
            description="Makes the desktop pet react when a clap is heard.",
            subscriptions=["audio_event"],
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.ctx.logger.info("ClapReactionPlugin initialized.")

    def on_event(self, event: IncomingEvent) -> None:
        if event.is_clap:
            self.ctx.logger.info("Clap detected! Triggering startled reaction.")
            self.ctx.send_emotion(emotion_id="startled", priority=200)
            self.ctx.send_speech("Whoa! That was loud!")
```

---

### Example 2: AI Screen Vision Assistant (`screen_qa.py`)

A multimodal plugin triggered by a global hotkey to capture screen context and ask Ollama:

```python
import threading
from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent

class ScreenAssistantPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="ScreenAssistant",
            version="1.0.0",
            description="Analyzes screen content on global hotkey press.",
            subscriptions=["hotkey:global_action_x"],
            required_capabilities=["ollama", "vision"],
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context

    def on_event(self, event: IncomingEvent) -> None:
        if event.hotkey_id == "global_action_x":
            self.ctx.send_emotion("curious", priority=150)
            self.ctx.send_speech("Let me see what you're working on...")
            
            # Offload AI reasoning to a background thread to avoid blocking IPC
            threading.Thread(target=self._analyze_screen, daemon=True).start()

    def _analyze_screen(self) -> None:
        if self.ctx.ai:
            response = self.ctx.ai.prompt("Summarize what the user is doing right now in 1 sentence.")
            self.ctx.send_speech(response)
            self.ctx.send_emotion("happy", priority=100)
```

---

### Example 3: Hourly Posture & Hydration Reminder (`posture_reminder.py`)

A polling plugin that uses `on_tick` for interval reminders:

```python
from core.base_plugin import BasePlugin, PluginManifest, PluginContext

class PostureReminderPlugin(BasePlugin):
    def __init__(self):
        self.elapsed = 0.0
        self.interval = 3600.0  # 1 hour

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="PostureReminder",
            version="1.0.0",
            description="Reminds the user to fix posture and drink water every hour.",
            tick_interval=10.0, # Check every 10 seconds
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context

    def on_tick(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.interval:
            self.elapsed = 0.0
            self.ctx.send_emotion("happy", priority=120)
            self.ctx.send_speech("Remember to stretch and drink water!")
```

---

## 4. Best Practices

1. **Non-Blocking Handlers**: `on_event` and `on_tick` run synchronously inside the dispatch loop. Never perform long computations, blocking network requests, or synchronous heavy LLM queries directly inside these methods. Always spawn a worker thread or use asynchronous tasks.
2. **Explicit Subscriptions**: Only subscribe to events your plugin actually needs.
3. **Stateless Fallbacks**: Check if `context.ai` is `None` before making LLM calls to allow plugins to degrade gracefully when Ollama is offline.
4. **Cleanup**: Always implement `on_unload` if your plugin spawns persistent threads, background timers, or file handles.
