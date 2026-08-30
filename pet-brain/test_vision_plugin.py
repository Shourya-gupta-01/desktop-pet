import logging
import time
from core.base_plugin import PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader
from core.ai_bridge import AIBridge
from core.emotion_engine import EmotionEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionTest")


class MockIPC:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)

    def send_command(self, msg):
        self.sent_messages.append(msg)


def main():
    logger.info("Starting Vision Plugin Test...")

    ipc = MockIPC()
    emotion_engine = EmotionEngine(ipc)
    ai = AIBridge()
    ok, msg, models = ai.health_check()
    logger.info(f"Ollama health: {ok} ({msg})")

    ctx = PluginContext(ipc=ipc, emotion_engine=emotion_engine, ai=ai)
    loader = PluginLoader(plugins_dir="plugins", context=ctx)
    loaded = loader.discover_and_load()

    vision_plugin = loaded.get("VisionChat")
    assert vision_plugin is not None, f"VisionChat plugin not loaded! Loaded: {list(loaded.keys())}"
    logger.info("[SUCCESS] VisionChat plugin loaded successfully!")

    # Test event dispatch
    event = IncomingEvent(
        event_type="input_event",
        data={"hotkey_id": "vision_action_v", "timestamp": 123456789},
    )

    logger.info("Dispatching vision_action_v event to VisionChat plugin...")
    loader.dispatch_event(event)

    logger.info("Waiting 10 seconds for LLaVA reasoning to complete...")
    time.sleep(10.0)

    logger.info(f"Emotions/Commands sent: {len(ipc.sent_messages)}")
    assert len(ipc.sent_messages) > 0, "No commands sent by VisionChat!"

    logger.info(">>> VISION CHAT PLUGIN TEST PASSED! <<<")


if __name__ == "__main__":
    main()
