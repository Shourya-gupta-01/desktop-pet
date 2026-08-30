import os
import sys
import shutil
import time
import logging

from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader


class MockIPCServer:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, msg):
        self.sent_messages.append(msg)


def test_plugin_loader():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("Test")
    
    mock_ipc = MockIPCServer()
    ctx = PluginContext(ipc=mock_ipc, ai=None, config={}, logger=logger)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    plugins_dir = os.path.join(base_dir, "plugins")

    loader = PluginLoader(plugins_dir=plugins_dir, context=ctx)
    plugins = loader.discover_and_load()

    logger.info(f"Loaded plugins: {list(plugins.keys())}")
    assert "HelloWorld" in plugins, "HelloWorld plugin should be loaded"
    assert "ClapReactor" in plugins, "ClapReactor plugin should be loaded"
    assert "HotkeyAction" in plugins, "HotkeyAction plugin should be loaded"
    assert "AICompanion" in plugins, "AICompanion plugin should be loaded"
    assert len(plugins) >= 4, f"Expected at least 4 plugins, found {len(plugins)}"

    # 1. Test InputEvent routing (Hotkey global_action_x)
    hotkey_event = IncomingEvent(
        event_type="input_event",
        data={"hotkey_id": "global_action_x", "timestamp": 12345},
    )
    mock_ipc.sent_messages.clear()
    loader.dispatch_event(hotkey_event)

    # Both HelloWorld (subscribed to input_event) and HotkeyAction (subscribed to hotkey:global_action_x) should have fired
    sent_types = [msg.WhichOneof("message_type") for msg in mock_ipc.sent_messages]
    logger.info(f"Messages sent after HotkeyEvent: {sent_types}")
    assert "speech_bubble" in sent_types, "HelloWorld should have sent speech_bubble"
    assert "emotion_command" in sent_types, "HotkeyAction should have sent emotion_command"

    # 2. Test AudioEvent routing (Clap)
    clap_event = IncomingEvent(
        event_type="audio_event",
        data={"amplitude": 0.85, "is_clap": True},
    )
    mock_ipc.sent_messages.clear()
    loader.dispatch_event(clap_event)

    sent_emotions = [
        msg.emotion_command.emotion_id
        for msg in mock_ipc.sent_messages
        if msg.WhichOneof("message_type") == "emotion_command"
    ]
    logger.info(f"Emotions sent after Clap: {sent_emotions}")
    assert "curious" in sent_emotions or "startled" in sent_emotions, "Clap should have triggered emotion"

    # 3. Test Dynamic Discovery: Add a 4th dummy plugin folder and reload
    dynamic_plugin_dir = os.path.join(plugins_dir, "dynamic_dummy")
    os.makedirs(dynamic_plugin_dir, exist_ok=True)
    
    with open(os.path.join(dynamic_plugin_dir, "manifest.yaml"), "w") as f:
        f.write("name: DynamicDummy\nversion: 0.0.1\nsubscriptions: [custom_test]\n")
        
    with open(os.path.join(dynamic_plugin_dir, "plugin.py"), "w") as f:
        f.write("""from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent
class DynamicDummyPlugin(BasePlugin):
    def get_manifest(self):
        return PluginManifest(name="DynamicDummy", subscriptions=["custom_test"])
    def on_event(self, event):
        self.ctx.send_speech("Dynamic dummy received event!")
    def on_load(self, ctx):
        self.ctx = ctx
""")

    try:
        # Create a fresh loader to simulate restarting pet-brain
        fresh_loader = PluginLoader(plugins_dir=plugins_dir, context=ctx)
        fresh_plugins = fresh_loader.discover_and_load()
        assert "DynamicDummy" in fresh_plugins, "4th dynamic plugin should be discovered with zero code changes!"
        logger.info("[SUCCESS] Dynamic plugin discovered automatically!")
    finally:
        # Cleanup temporary 4th plugin
        if os.path.exists(dynamic_plugin_dir):
            shutil.rmtree(dynamic_plugin_dir)

    loader.unload_all()
    print("\n>>> ALL PLUGIN LOADER TESTS PASSED SUCCESSFULLY! <<<\n")


if __name__ == "__main__":
    test_plugin_loader()
