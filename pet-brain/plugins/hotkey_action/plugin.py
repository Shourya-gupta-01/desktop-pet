from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class HotkeyActionPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="HotkeyAction",
            version="1.0.0",
            description="Specific hotkey handler that triggers curious sprite state.",
            subscriptions=["hotkey:dummy_test"],
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.ctx.logger.info("HotkeyActionPlugin loaded.")

    def on_event(self, event: IncomingEvent) -> None:
        if event.hotkey_id == "dummy_test":
            self.ctx.logger.info("dummy_test received! Setting curious emotion.")
            self.ctx.send_emotion("curious", priority=150, duration=3.0)
            self.ctx.send_speech("Curious what you're doing...")

    def on_unload(self) -> None:
        self.ctx.logger.info("HotkeyActionPlugin unloaded.")
