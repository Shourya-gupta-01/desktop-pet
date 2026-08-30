import time
import logging
from core.emotion_engine import EmotionEngine, VALID_EMOTIONS


class MockIPC:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)


def test_emotion_engine():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("EmotionTest")
    
    mock_ipc = MockIPC()
    engine = EmotionEngine(ipc_server=mock_ipc, default_emotion="idle")
    
    assert engine.get_current_emotion() == "idle"
    assert len(VALID_EMOTIONS) == 16, f"Expected 16 valid emotions, found {len(VALID_EMOTIONS)}"

    # 1. Request low priority emotion: "curious" (prio 80, duration 0.5s)
    logger.info("Requesting 'curious' (priority 80, duration 0.5s)...")
    engine.request_emotion("curious", priority=80, duration=0.5, source="TestPluginA")
    assert engine.get_current_emotion() == "curious"
    assert len(mock_ipc.sent_messages) == 1
    assert mock_ipc.sent_messages[-1].emotion_command.emotion_id == "curious"

    # 2. Immediately request higher priority emotion: "startled" (prio 200, duration 0.2s)
    logger.info("Requesting 'startled' (priority 200, duration 0.2s) -> Should override 'curious'")
    engine.request_emotion("startled", priority=200, duration=0.2, source="ClapPlugin")
    assert engine.get_current_emotion() == "startled"
    assert len(mock_ipc.sent_messages) == 2
    assert mock_ipc.sent_messages[-1].emotion_command.emotion_id == "startled"

    # 3. Fast-forward past 0.2s: "startled" should expire and resume "curious"
    logger.info("Sleeping 0.25s for 'startled' to expire...")
    time.sleep(0.25)
    engine.tick(0.25)
    
    assert engine.get_current_emotion() == "curious", f"Expected 'curious' to resume, got '{engine.get_current_emotion()}'"
    assert len(mock_ipc.sent_messages) == 3
    assert mock_ipc.sent_messages[-1].emotion_command.emotion_id == "curious"
    logger.info("-> Successfully resumed 'curious'!")

    # 4. Fast-forward past 0.35s: "curious" should expire and decay to "idle"
    logger.info("Sleeping 0.35s for 'curious' to expire...")
    time.sleep(0.35)
    engine.tick(0.35)

    assert engine.get_current_emotion() == "idle", f"Expected 'idle' fallback, got '{engine.get_current_emotion()}'"
    assert len(mock_ipc.sent_messages) == 4
    assert mock_ipc.sent_messages[-1].emotion_command.emotion_id == "idle"
    logger.info("-> Successfully decayed to 'idle'!")

    # 5. Test unknown emotion fallback
    engine.request_emotion("non_existent_emotion", priority=100, duration=1.0)
    assert engine.get_current_emotion() == "curious" # Safe fallback

    print("\n>>> ALL EMOTION ENGINE TESTS PASSED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    test_emotion_engine()
