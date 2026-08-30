from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
import logging
import time
import sys
import os

# Ensure pet_pb2 can be imported from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pet_pb2


@dataclass
class PluginManifest:
    """
    Metadata and declared capabilities of a plugin.
    Used by PluginLoader for discovery, filtering, and event routing.
    """
    name: str
    version: str = "0.1.0"
    author: str = "Anonymous"
    description: str = ""
    # Subscriptions: list of event names to receive ("input_event", "audio_event", "screen_frame", "*")
    # Can also match specific hotkey IDs like "hotkey:global_action_x"
    subscriptions: List[str] = field(default_factory=list)
    # If set, on_tick(dt) is invoked at approximately this interval (in seconds)
    tick_interval: Optional[float] = None
    # Declared capability requirements (e.g., ["ollama", "vision", "microphone"])
    required_capabilities: List[str] = field(default_factory=list)


@dataclass
class IncomingEvent:
    """
    A normalized event forwarded from the Rust shell or internal event loop.
    """
    event_type: str  # "input_event", "audio_event", "screen_frame", "custom"
    raw_message: Optional[pet_pb2.PetMessage] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def is_hotkey(self) -> bool:
        return self.event_type == "input_event"

    @property
    def is_audio(self) -> bool:
        return self.event_type == "audio_event"

    @property
    def is_clap(self) -> bool:
        return self.event_type == "audio_event" and self.data.get("is_clap", False)

    @property
    def hotkey_id(self) -> Optional[str]:
        return self.data.get("hotkey_id")


@dataclass
class PluginContext:
    """
    Execution context provided to plugins on load.
    Encapsulates communication, AI access, scoped logging, and persistent configuration.
    """
    ipc: Any  # IPCServer instance
    ai: Optional[Any] = None  # AIBridge instance (for LLM / Ollama interactions)
    config: Dict[str, Any] = field(default_factory=dict)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("Plugin"))
    state: Dict[str, Any] = field(default_factory=dict)

    def send_emotion(self, emotion_id: str, priority: int = 100) -> None:
        """
        Request a sprite / emotion state change on the Rust desktop pet shell.
        
        :param emotion_id: Emotion identifier corresponding to asset folder (e.g., "happy", "startled", "curious", "idle")
        :param priority: Priority level (0-255). Higher priority overrides lower priority emotions.
        """
        msg = pet_pb2.PetMessage()
        msg.emotion_command.emotion_id = emotion_id
        msg.emotion_command.priority = priority
        self.ipc.send_message(msg)

    def send_speech(self, text: str, is_streaming: bool = False) -> None:
        """
        Display text in a speech bubble above the desktop pet.
        
        :param text: Text content or streaming token chunk
        :param is_streaming: True if this is an incremental streaming token chunk
        """
        msg = pet_pb2.PetMessage()
        msg.speech_bubble.text = text
        msg.speech_bubble.is_streaming_chunk = is_streaming
        self.ipc.send_message(msg)

    def send_raw_message(self, message: pet_pb2.PetMessage) -> None:
        """Send any arbitrary Protobuf PetMessage directly to the Rust shell."""
        self.ipc.send_message(message)


class BasePlugin(ABC):
    """
    Abstract base class that all Desktop Pet plugins must implement.
    Defines the contract for discovery, initialization, event handling, and teardown.
    """

    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """
        Return the plugin's metadata, event subscriptions, and required capabilities.
        Must be implemented by every plugin.
        """
        pass

    def on_load(self, context: PluginContext) -> None:
        """
        Called once when the plugin is loaded and initialized.
        Store the context, load custom assets, or prepare local state here.
        """
        pass

    def on_event(self, event: IncomingEvent) -> None:
        """
        Called whenever a subscribed event occurs (e.g. global hotkey pressed, clap detected).
        Heavy AI processing should be offloaded asynchronously to avoid blocking the event loop.
        """
        pass

    def on_tick(self, dt: float) -> None:
        """
        Optional polling hook called periodically if manifest.tick_interval is defined.
        
        :param dt: Delta time in seconds elapsed since the last tick.
        """
        pass

    def on_unload(self) -> None:
        """
        Called when the plugin is being unloaded or when pet-brain shuts down.
        Clean up background threads, network connections, or file handles here.
        """
        pass
