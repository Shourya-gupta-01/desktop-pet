import time
import subprocess
from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class VoiceChatPlugin(BasePlugin):
    """
    Unified Voice, Vision & Push-to-Talk Companion Plugin:
    - Hold Super+Z: Listens while held, processes when released.
    - Double Clap Toggle: Clap once to start speaking, clap again when finished.
    - Multimodal Awareness: Automatically captures screen and answers using LLaVA (if visual question) or Mistral.
    - Unlimited Tokens: Never cuts off sentences mid-thought.
    """

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="VoiceChat",
            version="1.0.0",
            description="Unified Super+Z push-to-talk, clap toggle, and multimodal vision & voice AI companion.",
            subscriptions=[
                "hotkey:voice_press",
                "hotkey:voice_release",
                "audio_event",
                "hotkey:voice_action_z",
            ],
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.is_recording = False
        self.is_processing = False
        self.ctx.logger.info("VoiceChatPlugin loaded! Ready for Super+Z and Clap-to-Talk.")

    def on_event(self, event: IncomingEvent) -> None:
        # 1. Acoustic Clap Toggle (Clap to start, clap again to stop!)
        if event.is_clap:
            self.ctx.logger.info("Clap event received in VoiceChat!")
            if not self.is_recording and not self.is_processing:
                # First Clap -> Start recording!
                self.is_recording = True
                self.ctx.logger.info("Clap toggle: Starting microphone stream...")
                self.ctx.send_emotion("curious", priority=160, duration=35.0)
                self.ctx.send_speech("Listening... 🎙️ (clap again when done)")

                if not self.ctx.stt:
                    self.ctx.send_speech("Voice recognition offline.")
                    self.is_recording = False
                    return

                self.ctx.stt.start_push_to_talk()
            elif self.is_recording and not self.is_processing:
                # Second Clap -> Stop recording and process!
                self.is_recording = False
                self.is_processing = True
                self.ctx.logger.info("Clap toggle: Stopping microphone stream and transcribing...")
                self.ctx.send_speech("Thinking...")

                if not self.ctx.stt:
                    self.is_processing = False
                    return

                self.ctx.stt.stop_push_to_talk(callback=self._handle_transcribed_text)
            return

        hotkey = event.hotkey_id

        # 2. Push-To-Talk PRESS (Holding Super + Z down)
        if hotkey == "voice_press":
            if self.is_processing or self.is_recording:
                return

            self.is_recording = True
            self.ctx.logger.info("Voice PTT press: Starting microphone stream...")
            self.ctx.send_emotion("curious", priority=160, duration=35.0)
            self.ctx.send_speech("Listening... 🎙️ (speak now)")

            if not self.ctx.stt:
                self.ctx.logger.warning("STT Engine is unavailable.")
                self.ctx.send_speech("Voice recognition offline.")
                self.is_recording = False
                return

            self.ctx.stt.start_push_to_talk()

        # 3. Push-To-Talk RELEASE (User let go of Super + Z)
        elif hotkey == "voice_release":
            if not self.is_recording or self.is_processing:
                return

            self.is_recording = False
            self.is_processing = True
            self.ctx.logger.info("Voice PTT release: Stopping microphone and transcribing...")
            self.ctx.send_speech("Thinking...")

            if not self.ctx.stt:
                self.is_processing = False
                return

            self.ctx.stt.stop_push_to_talk(callback=self._handle_transcribed_text)

        # 4. Fallback Tap Mode (Ctrl+Alt+Shift+Z)
        elif hotkey == "voice_action_z":
            if self.is_processing or self.is_recording:
                return

            self.is_processing = True
            self.ctx.logger.info("voice_action_z triggered! Listening with VAD...")
            self.ctx.send_emotion("curious", priority=160, duration=30.0)
            self.ctx.send_speech("Listening... (speak now)")

            if not self.ctx.stt:
                self.ctx.send_speech("Voice recognition offline.")
                self.is_processing = False
                return

            def on_speech_started():
                self.ctx.send_speech("Listening... 🎙️")

            self.ctx.stt.record_and_transcribe(
                max_duration_sec=8.0,
                silence_timeout_sec=1.3,
                initial_silence_timeout_sec=3.5,
                on_speech_started=on_speech_started,
                callback=self._handle_transcribed_text,
            )

    def _handle_transcribed_text(self, text: str):
        if not text or len(text.strip()) == 0:
            self.ctx.logger.info("No speech detected.")
            self.ctx.send_speech("(didn't catch that...)")
            self.ctx.send_emotion("idle", priority=160, duration=1.0)
            self.is_processing = False
            self.is_recording = False
            return

        self.ctx.logger.info(f"User said: '{text}'")
        self.ctx.send_emotion("curious", priority=150, duration=35.0)
        self.ctx.send_speech("Thinking...")

        if not self.ctx.ai:
            self.ctx.send_speech(f"Heard: '{text}' (AI offline)")
            self.is_processing = False
            self.is_recording = False
            return

        # Check if the query refers to screen / visuals
        text_lower = text.lower()
        visual_keywords = [
            "screen", "look", "see", "this", "read", "code", "window",
            "what is this", "what do you see", "describe", "image", "error",
            "app", "browser", "page"
        ]
        is_visual_query = any(k in text_lower for k in visual_keywords)

        first_token = [True]

        def on_token(chunk: str):
            if first_token[0]:
                self.ctx.send_speech(chunk, is_streaming=False)
                first_token[0] = False
            else:
                self.ctx.send_speech(chunk, is_streaming=True)
            # Natural dialogue reading speed
            time.sleep(0.02)

        def on_complete(response: str):
            self.ctx.logger.info(f"AI response: {response}")
            self.ctx.send_emotion("happy", priority=120, duration=15.0)
            self.is_processing = False
            self.is_recording = False

        if is_visual_query:
            # Capture screen in memory and pass to LLaVA
            try:
                self.ctx.logger.info("Visual query detected! Capturing screen for LLaVA...")
                capture = subprocess.run(
                    ["grim", "-t", "jpeg", "-q", "55", "-"],
                    capture_output=True,
                    timeout=5.0,
                )
                if capture.returncode == 0:
                    image_bytes = capture.stdout
                    vision_prompt = (
                        f"The user asked while looking at their desktop screen: '{text}'. "
                        "You are a friendly, witty chibi anime companion. Look at their screen and give a complete, helpful, natural answer in 1 or 2 sentences."
                    )
                    self.ctx.ai.prompt_vision_async(
                        prompt=vision_prompt,
                        image_bytes=image_bytes,
                        callback=on_complete,
                        on_token=on_token,
                    )
                    return
                else:
                    self.ctx.logger.warning("grim failed, falling back to Mistral text prompt.")
            except Exception as e:
                self.ctx.logger.warning(f"Error capturing screen for vision: {e}")

        # General conversational prompt via Mistral
        prompt_text = (
            f"The user said: '{text}'. "
            "You are a friendly, cute chibi anime companion. Give a complete, lively, natural answer in 1 or 2 sentences."
        )

        self.ctx.ai.prompt_async(
            text=prompt_text,
            callback=on_complete,
            on_token=on_token,
            options=None,  # Unlimited token generation
        )

    def on_unload(self) -> None:
        self.ctx.logger.info("VoiceChatPlugin unloaded.")
