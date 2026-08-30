import logging
import time
import numpy as np
from core.base_plugin import PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader
from core.ai_bridge import AIBridge
from core.emotion_engine import EmotionEngine
from core.stt_engine import STTEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceTest")


class MockIPC:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)

    def send_command(self, msg):
        self.sent_messages.append(msg)


def main():
    logger.info("Starting Voice Plugin Test...")

    ipc = MockIPC()
    emotion_engine = EmotionEngine(ipc)
    ai = AIBridge()
    ok, msg, models = ai.health_check()
    logger.info(f"Ollama health: {ok} ({msg})")

    stt = STTEngine(model_size="tiny.en")
    
    # 1. Test faster-whisper on synthetic audio array (silent/noise buffer)
    logger.info("Testing STT engine with 1.0s synthetic audio buffer...")
    sample_rate = 16000
    dummy_audio = np.zeros(sample_rate, dtype=np.float32)
    transcription = stt.transcribe_audio_array(dummy_audio, sample_rate=sample_rate)
    logger.info(f"Synthetic transcription test complete (result: '{transcription}')")

    # 2. Test PluginLoader discovery for VoiceChat
    ctx = PluginContext(ipc=ipc, emotion_engine=emotion_engine, ai=ai, stt=stt)
    loader = PluginLoader(plugins_dir="plugins", context=ctx)
    loaded = loader.discover_and_load()

    voice_plugin = loaded.get("VoiceChat")
    assert voice_plugin is not None, f"VoiceChat plugin not loaded! Loaded: {list(loaded.keys())}"
    logger.info("[SUCCESS] VoiceChat plugin loaded successfully!")

    # 3. Test event dispatch
    event = IncomingEvent(
        event_type="input_event",
        data={"hotkey_id": "voice_action_z", "timestamp": 123456789},
    )

    logger.info("Dispatching voice_action_z event to VoiceChat plugin...")
    loader.dispatch_event(event)

    # Check that speech bubble / emotion was triggered
    assert len(ipc.sent_messages) > 0, "No commands sent by VoiceChat on trigger!"
    logger.info(f"Commands sent on trigger: {len(ipc.sent_messages)}")

    logger.info(">>> VOICE CHAT & STT ENGINE TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    main()
