import logging
from core.base_plugin import PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader
from core.emotion_engine import EmotionEngine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OSNavTest")


class MockIPC:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)

    def send_command(self, msg):
        self.sent_messages.append(msg)


def main():
    logger.info("Starting Strict App, Command & Compound URL Action Tests...")

    ipc = MockIPC()
    emotion_engine = EmotionEngine(ipc)
    ctx = PluginContext(ipc=ipc, emotion_engine=emotion_engine)

    # 1. Test PluginLoader discovery & dynamic indexing
    loader = PluginLoader(plugins_dir="plugins", context=ctx)
    loaded = loader.discover_and_load()

    os_plugin = loaded.get("OSNavigation")
    assert os_plugin is not None, f"OSNavigation plugin not found! Loaded: {list(loaded.keys())}"
    logger.info(f"[SUCCESS] OSNavigation plugin loaded! Total indexed app triggers: {len(os_plugin.app_index)}")

    # 2. REQUIREMENT 1: Strict Native Application Launches (Must open native app, NOT web browser!)
    test_native_apps = [
        "open spotify", "open discord", "open steam", "open chrome", "open brave", "open terminal",
        "Open file manager.", "Open file manager for me.", "open app file manager", "launch file manager", "open spotify."
    ]
    for app_cmd in test_native_apps:
        handled, reply, emotion = os_plugin.handle_query(app_cmd)
        logger.info(f"Native App Query '{app_cmd}' -> Handled: {handled}, Reply: {reply}")
        assert handled, f"Failed to resolve native application: '{app_cmd}'"
        assert "Opening" in reply or "Opened" in reply, f"Expected app launch message: {reply}"

    # 3. REQUIREMENT 2: Strict Command Execution (Runs in terminal)
    test_commands = [
        ("run cargo check", "cargo check"),
        ("run python main.py", "python main.py"),
        ("run git status", "git status"),
        ("in terminal run htop", "htop"),
        ("run command ls -la", "ls -la")
    ]
    for query, expected_cmd in test_commands:
        handled, reply, emotion = os_plugin.handle_query(query)
        logger.info(f"Command Query '{query}' -> Handled: {handled}, Reply: {reply}")
        assert handled, f"Failed to execute command: '{query}'"
        assert "Running '" in reply and expected_cmd in reply, f"Expected terminal execution reply: {reply}"

    # 4. REQUIREMENT 3: Compound URL + Action on URL
    test_compound_urls = [
        ("open youtube.com and search for lofi hip hop", "lofi hip hop"),
        ("open github.com and search for whisper", "whisper"),
        ("open google.com and search for rust tutorials", "rust tutorials")
    ]
    for query, expected_term in test_compound_urls:
        handled, reply, emotion = os_plugin.handle_query(query)
        logger.info(f"Compound URL Query '{query}' -> Handled: {handled}, Reply: {reply}")
        assert handled, f"Failed to handle compound URL query: '{query}'"
        assert expected_term in reply, f"Expected search term in reply: {reply}"

    # 5. Direct URL / Domain opening
    handled, reply, emotion = os_plugin.handle_query("open github.com")
    assert handled and "github.com" in reply, f"Direct domain failed: {reply}"
    logger.info(f"[SUCCESS] Direct domain response: {reply}")

    # 6. SSD / Disk Space Telemetry Queries
    handled, reply, emotion = os_plugin.handle_query("how much disk space do I have?")
    assert handled and ("Disk:" in reply or "SSD Storage:" in reply or "Storage:" in reply), f"Disk space query failed: {reply}"
    logger.info(f"[SUCCESS] Disk space query response: {reply} (Emotion: {emotion})")

    # 7. Disambiguation (Conversational & Screen queries must NOT be falsely triggered)
    handled, _, _ = os_plugin.handle_query("read this code on my screen")
    assert not handled, "Screen code reading query should NOT be captured as an app launch!"
    logger.info("[SUCCESS] 'read this code on my screen' correctly passed to vision AI!")

    logger.info(">>> ALL STRICT APP, COMMAND & COMPOUND URL TESTS PASSED! <<<")


if __name__ == "__main__":
    main()
