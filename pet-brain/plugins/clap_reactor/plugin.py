from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class ClapReactorPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="ClapReactor",
            version="1.0.0",
            description="Listens for acoustic claps and triggers startled reactions.",
            subscriptions=["audio_event"],
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.ctx.logger.info("ClapReactorPlugin loaded and listening for audio events.")

    def on_event(self, event: IncomingEvent) -> None:
        if event.is_clap:
            self.ctx.logger.info(f"Clap detected! (Amplitude: {event.data.get('amplitude', 0.0):.3f})")
            self.ctx.send_emotion("startled", priority=200, duration=3.0)
            self.ctx.send_speech("Whoa! Did you just clap?")

    def on_unload(self) -> None:
        self.ctx.logger.info("ClapReactorPlugin unloaded.")
