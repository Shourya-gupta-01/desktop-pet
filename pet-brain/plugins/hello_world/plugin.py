from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class HelloWorldPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="HelloWorld",
            version="1.0.0",
            description="Basic greeting plugin",
            subscriptions=["input_event"],
            tick_interval=10.0,
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.ctx.logger.info("HelloWorldPlugin loaded and active!")

    def on_event(self, event: IncomingEvent) -> None:
        self.ctx.logger.info(f"HelloWorld received event: {event.event_type} (hotkey: {event.hotkey_id})")
        self.ctx.send_speech("Hello from HelloWorld plugin!")

    def on_tick(self, dt: float) -> None:
        self.ctx.logger.debug(f"HelloWorld tick! (dt={dt:.1f}s)")

    def on_unload(self) -> None:
        self.ctx.logger.info("HelloWorldPlugin shutting down.")
