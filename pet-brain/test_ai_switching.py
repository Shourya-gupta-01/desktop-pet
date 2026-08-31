import os
import logging
from core.ai_bridge import AIBridge
from core.base_plugin import PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader
from core.emotion_engine import EmotionEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AISwitchTest")


class MockIPC:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)

    def send_command(self, msg):
        self.sent_messages.append(msg)


def main():
    logger.info("Starting AI Backend Switching & Gemini Hybrid Test...")

    # 1. Test AIBridge Multi-Backend Initialization
    ai = AIBridge(backend="local")
    assert ai.backend == "local", "Default backend should be 'local'"
    logger.info("[SUCCESS] AIBridge initialized with Local backend!")

    # 2. Test switching to Gemini without API key
    ai_no_key = AIBridge(backend="local")
    ai_no_key.reload_config = lambda: None
    ai_no_key.gemini_api_key = ""
    success, msg = ai_no_key.set_backend("gemini")
    assert not success and "GEMINI_API_KEY is not set" in msg, f"Expected key failure, got: {msg}"
    logger.info(f"[SUCCESS] Handled missing API key properly: {msg}")

    # 3. Test switching to Gemini with API key
    ai.gemini_api_key = "mock_unit_test_key_12345"
    success, msg = ai.set_backend("gemini")
    assert success and ai.backend == "gemini", f"Expected successful switch to gemini, got: {msg}"
    logger.info(f"[SUCCESS] Switched to Gemini: {msg}")

    # 4. Test 1-click Toggle
    new_backend, msg = ai.toggle_backend()
    assert new_backend == "local", "Toggling from gemini should switch to local"
    logger.info(f"[SUCCESS] 1-Click Toggled to: {new_backend} ({msg})")

    new_backend, msg = ai.toggle_backend()
    assert new_backend == "gemini", "Toggling from local should switch to gemini"
    logger.info(f"[SUCCESS] 1-Click Toggled to: {new_backend} ({msg})")

    # 5. Test VoiceChat Plugin Voice Switching
    ipc = MockIPC()
    emotion_engine = EmotionEngine(ipc)
    ctx = PluginContext(ipc=ipc, emotion_engine=emotion_engine, ai=ai)

    loader = PluginLoader(plugins_dir="plugins", context=ctx)
    loaded = loader.discover_and_load()
    voice_plugin = loaded.get("VoiceChat")
    assert voice_plugin is not None, "VoiceChat plugin must be loaded"

    # Test voice command "switch to local"
    voice_plugin._handle_transcribed_text("switch to local")
    assert ai.backend == "local", "Voice command 'switch to local' should set backend to local"
    logger.info("[SUCCESS] Voice command 'switch to local' switched backend to local!")

    # Test voice command "switch to gemini"
    voice_plugin._handle_transcribed_text("switch to gemini")
    assert ai.backend == "gemini", "Voice command 'switch to gemini' should set backend to gemini"
    logger.info("[SUCCESS] Voice command 'switch to gemini' switched backend to gemini!")

    # 6. Test 1-Click Hotkey / IPC Event Toggle
    toggle_event = IncomingEvent(
        event_type="input_event",
        data={"hotkey_id": "toggle_ai"},
    )
    loader.dispatch_event(toggle_event)
    assert ai.backend == "local", "1-Click IPC toggle event should switch from gemini to local"
    logger.info("[SUCCESS] 1-Click IPC Event toggled backend to local!")

    ai.shutdown()
    logger.info(">>> ALL AI BACKEND SWITCHING & GEMINI HYBRID TESTS PASSED! <<<")


if __name__ == "__main__":
    main()
