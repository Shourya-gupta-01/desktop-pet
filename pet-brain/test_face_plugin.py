import logging
import numpy as np
from core.base_plugin import PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader
from core.emotion_engine import EmotionEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FaceTest")


class MockIPC:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)

    def send_command(self, msg):
        self.sent_messages.append(msg)


def main():
    logger.info("Starting FaceVerify Plugin Test...")

    ipc = MockIPC()
    emotion_engine = EmotionEngine(ipc)
    ctx = PluginContext(ipc=ipc, emotion_engine=emotion_engine)

    # 1. Test PluginLoader discovery
    loader = PluginLoader(plugins_dir="plugins", context=ctx)
    loaded = loader.discover_and_load()

    face_plugin = loaded.get("FaceVerify")
    assert face_plugin is not None, f"FaceVerify plugin not found! Loaded: {list(loaded.keys())}"
    logger.info("[SUCCESS] FaceVerify plugin loaded successfully!")

    # 2. Test YuNet detector initialization
    assert face_plugin.detector is not None, "YuNet ONNX detector should be initialized!"
    logger.info("[SUCCESS] YuNet ONNX detector initialized!")

    # 3. Test detection logic on synthetic blank image
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    has_face = face_plugin._detect_face(dummy_frame)
    assert not has_face, "Synthetic black frame should have no face detected"
    logger.info("[SUCCESS] Synthetic detection evaluated cleanly (no false positives)!")

    # 4. Test Manual Event trigger
    event = IncomingEvent(
        event_type="input_event",
        data={"hotkey_id": "face_scan", "timestamp": 123456789},
    )
    loader.dispatch_event(event)
    logger.info("Manual face_scan event dispatched successfully!")

    logger.info(">>> ALL FACE VERIFY PLUGIN TESTS PASSED! <<<")


if __name__ == "__main__":
    main()
