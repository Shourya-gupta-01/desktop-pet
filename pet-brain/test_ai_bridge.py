import os
import sys
import time
import logging

from core.ai_bridge import AIBridge
from core.base_plugin import PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader


class MockIPCServer:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)


def test_ai_bridge_and_concurrency():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("AITest")

    logger.info("--- Testing AIBridge Health-Check ---")
    bridge = AIBridge()
    is_healthy, status_msg, models = bridge.health_check()
    logger.info(f"Health status: {is_healthy}, message: {status_msg}, models: {models}")
    assert is_healthy, f"Expected Ollama to be healthy: {status_msg}"

    logger.info("--- Testing Synchronous AI Prompt ---")
    response = bridge.prompt("Reply with only the single word 'READY'.", model="mistral:latest")
    logger.info(f"Synchronous LLM Response: {response}")
    assert len(response) > 0, "Expected non-empty response from Ollama"

    logger.info("--- Testing Non-Blocking Concurrency ---")
    mock_ipc = MockIPCServer()
    ctx = PluginContext(ipc=mock_ipc, ai=bridge, config={}, logger=logger)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    plugins_dir = os.path.join(base_dir, "plugins")
    loader = PluginLoader(plugins_dir=plugins_dir, context=ctx)
    plugins = loader.discover_and_load()

    assert "AICompanion" in plugins, "AICompanion plugin should be loaded"
    assert "ClapReactor" in plugins, "ClapReactor plugin should be loaded"

    # Step 1: Fire a slow LLM generation via AICompanion in background
    ai_completed = []
    def ai_callback(res):
        ai_completed.append(res)
        logger.info(f"[Background AI Worker] Generated: {res}")

    logger.info("Triggering slow background AI generation...")
    ai_future = bridge.prompt_async(
        "Write a 2-paragraph creative story about a tiny anime pet living in a Linux Hyprland desktop window.",
        callback=ai_callback,
        model="mistral:latest",
    )

    # Step 2: Concurrently dispatch rapid hotkey & audio events while AI is running
    logger.info("Dispatching rapid hotkey and audio events during active AI generation...")
    start_time = time.time()
    num_events = 20
    
    for i in range(num_events):
        event_start = time.time()
        # Alternate between hotkey and clap
        if i % 2 == 0:
            ev = IncomingEvent(event_type="input_event", data={"hotkey_id": "test_fast", "timestamp": time.time()})
        else:
            ev = IncomingEvent(event_type="audio_event", data={"amplitude": 0.9, "is_clap": True})

        loader.dispatch_event(ev)
        elapsed_ms = (time.time() - event_start) * 1000.0
        assert elapsed_ms < 15.0, f"Event {i} took {elapsed_ms:.2f}ms (blocked by AI!)"

    total_dispatch_time = time.time() - start_time
    logger.info(f"Dispatched {num_events} events in {total_dispatch_time*1000:.2f}ms total (Average {total_dispatch_time*1000/num_events:.2f}ms per event)")

    # Step 3: Wait for background AI generation to complete
    logger.info("Waiting for background AI generation to complete...")
    ai_result = ai_future.result(timeout=60.0)
    assert len(ai_result) > 20, "Expected full creative response from Ollama"
    assert len(ai_completed) == 1, "Callback should have fired once"

    logger.info(f"AI Generation finished with {len(ai_result)} characters.")
    logger.info("\n>>> ALL AI BRIDGE CONCURRENCY TESTS PASSED SUCCESSFULLY! <<<\n")

    loader.unload_all()
    bridge.shutdown()


if __name__ == "__main__":
    test_ai_bridge_and_concurrency()
