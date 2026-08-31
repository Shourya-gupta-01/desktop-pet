from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class AICompanionPlugin(BasePlugin):
    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="AICompanion",
            version="1.0.0",
            description="Demonstrates threaded Ollama streaming and AI reasoning on hotkey triggers.",
            subscriptions=["hotkey:global_action_x"],
            required_capabilities=["ollama"],
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.ctx.logger.info("AICompanionPlugin loaded! Ready for LLM interactions.")

    def on_event(self, event: IncomingEvent) -> None:
        if event.hotkey_id == "global_action_x":
            self.ctx.logger.info("AICompanion triggered via hotkey!")
            self.ctx.send_emotion("curious", priority=150, duration=15.0)
            self.ctx.send_speech("Thinking...")

            if not self.ctx.ai:
                self.ctx.logger.warning("AI Bridge is unavailable (Ollama is offline).")
                self.ctx.send_speech("Ollama is offline! Please start Ollama.")
                return

            prompt_text = "You are Roronoa Zoro from One Piece. Give a quick, badass, one-sentence greeting to your Captain or Nakama (maybe mention your swords, training, or getting lost)!"

            first_token = [True]

            def on_token(chunk: str):
                if first_token[0]:
                    # Clear "Thinking..." and set first token
                    self.ctx.send_speech(chunk, is_streaming=False)
                    first_token[0] = False
                else:
                    self.ctx.send_speech(chunk, is_streaming=True)

            def on_complete(response: str):
                self.ctx.logger.info(f"AI Response generated: {response}")
                self.ctx.send_emotion("happy", priority=120, duration=6.0)

            # Fire the request asynchronously on the AIBridge worker pool
            self.ctx.ai.prompt_async(
                text=prompt_text,
                callback=on_complete,
                on_token=on_token,
                options=None,  # Unlimited token generation
            )

    def on_unload(self) -> None:
        self.ctx.logger.info("AICompanionPlugin unloaded.")
