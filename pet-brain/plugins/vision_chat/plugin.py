import subprocess
from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class VisionChatPlugin(BasePlugin):
    """
    Vision Chat Plugin:
    Captures the current desktop screen on Wayland via grim, passes the image bytes
    to local LLaVA via AIBridge, and streams real-time visual observations into the speech bubble.
    """

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="VisionChat",
            version="1.0.0",
            description="Captures desktop screen and prompts local LLaVA for visual observations.",
            subscriptions=["hotkey:vision_action_v"],
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.ctx.logger.info("VisionChatPlugin loaded! Ready for desktop visual analysis.")

    def on_event(self, event: IncomingEvent) -> None:
        if event.hotkey_id == "vision_action_v":
            self.ctx.logger.info("vision_action_v triggered! Capturing screen...")

            self.ctx.send_emotion("curious", priority=150, duration=25.0)
            self.ctx.send_speech("Looking at your screen...")

            if not self.ctx.ai:
                self.ctx.logger.warning("AI Bridge is unavailable (Ollama is offline).")
                self.ctx.send_speech("AI is offline! Please ensure Ollama is running.")
                return

            # Capture desktop screen in memory using native Wayland grim
            try:
                capture = subprocess.run(
                    ["grim", "-t", "jpeg", "-q", "55", "-"],
                    capture_output=True,
                    timeout=5.0,
                )
                if capture.returncode != 0:
                    err_msg = capture.stderr.decode().strip()
                    self.ctx.logger.error(f"grim screen capture failed: {err_msg}")
                    self.ctx.send_speech(f"Screen capture failed: {err_msg}")
                    return

                image_bytes = capture.stdout
                self.ctx.logger.info(f"Screen captured successfully ({len(image_bytes)} bytes). Sending to LLaVA...")

            except Exception as e:
                self.ctx.logger.error(f"Exception during screen capture: {e}")
                self.ctx.send_speech(f"Capture error: {e}")
                return

            prompt_text = (
                "You are a cute, witty anime chibi desktop pet watching your human's screen. "
                "In one or two short sentences, make a fun, clever observation about what they are doing or looking at right now."
            )

            first_token = [True]

            def on_token(chunk: str):
                if first_token[0]:
                    # Replace "Looking at your screen..." on the first received token
                    self.ctx.send_speech(chunk, is_streaming=False)
                    first_token[0] = False
                else:
                    self.ctx.send_speech(chunk, is_streaming=True)

            def on_complete(response: str):
                self.ctx.logger.info(f"Vision AI Response: {response}")
                self.ctx.send_emotion("happy", priority=120, duration=6.0)

            # Prompt LLaVA asynchronously on thread pool
            self.ctx.ai.prompt_vision_async(
                prompt=prompt_text,
                image_bytes=image_bytes,
                callback=on_complete,
                on_token=on_token,
            )

    def on_unload(self) -> None:
        self.ctx.logger.info("VisionChatPlugin unloaded.")
