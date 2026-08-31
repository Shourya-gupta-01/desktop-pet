import time
import subprocess
from typing import Optional
import cv2
import numpy as np
from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class VoiceChatPlugin(BasePlugin):
    """
    Unified Voice, Dual-Vision & Push-to-Talk Companion Plugin:
    - Hold Super+Z: Listens while held, processes when released.
    - Double Clap Toggle: Clap once to start speaking, clap again when finished.
    - Dual Visual Perception (Webcam + Screen):
        * Asks about face/user/room/glasses/camera -> captures webcam via OpenCV.
        * Asks about screen/code/app/windows -> captures desktop via grim.
    - Qwen2.5-VL 7B on GPU: High-accuracy multimodal vision and text reasoning.
    - Unlimited Tokens: Streams complete, natural thoughts without truncation.
    """

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="VoiceChat",
            version="1.0.0",
            description="Unified Super+Z push-to-talk, clap toggle, and dual vision (webcam + screen) with Qwen2.5-VL 7B.",
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
        self.ctx.logger.info("VoiceChatPlugin loaded! Ready for Super+Z, Clap-to-Talk, and Dual Vision.")

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
                self.ctx.send_speech("Voice recognition offline.")
                self.is_processing = False
                return

            self.ctx.stt.stop_push_to_talk(callback=self._handle_transcribed_text)

        # 4. Instant 1-Click / Hotkey AI Backend Toggle (Local <-> Gemini)
        elif hotkey == "toggle_ai" or event.event_type == "ai_toggle":
            backend, msg = self.ctx.ai.toggle_backend()
            self.ctx.logger.info(f"AI Backend toggled to: {backend}")
            self.ctx.send_emotion("excited" if backend == "gemini" else "happy", priority=150, duration=8.0)
            self.ctx.send_speech(msg)

        # 5. Fallback Single-Trigger (voice_action_z)
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

    def _capture_webcam(self) -> Optional[bytes]:
        """Capture a single frame from the webcam in volatile RAM with optimized V4L2 backend."""
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None

            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return None

            # Resize to 384x288 to drastically reduce vision tokens and cut inference latency by 4x
            small = cv2.resize(frame, (384, 288))
            success, buffer = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
            return buffer.tobytes() if success else None
        except Exception as e:
            self.ctx.logger.warning(f"Webcam capture failed: {e}")
            return None

    def _capture_screen(self) -> Optional[bytes]:
        """Capture the current Wayland desktop screen in volatile RAM with full native resolution."""
        try:
            capture = subprocess.run(
                ["grim", "-t", "jpeg", "-q", "75", "-"],
                capture_output=True,
                timeout=5.0,
            )
            if capture.returncode == 0 and capture.stdout:
                return capture.stdout
            return None
        except Exception as e:
            self.ctx.logger.warning(f"Screen capture failed: {e}")
            return None

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

        text_lower = text.lower()

        # 0. OS Navigation / System Control Fast-Path
        # Check for instant AI backend switching commands (Gemini vs Local)
        if any(w in text_lower for w in ["switch to gemini", "use gemini", "enable gemini", "switch to cloud"]):
            success, msg = self.ctx.ai.set_backend("gemini")
            self.ctx.send_emotion("excited" if success else "confused", priority=140, duration=8.0)
            self.ctx.send_speech(msg)
            self.is_processing = False
            self.is_recording = False
            return

        if any(w in text_lower for w in ["switch to local", "use local", "use ollama", "use qwen", "go offline", "switch to offline"]):
            success, msg = self.ctx.ai.set_backend("local")
            self.ctx.send_emotion("happy", priority=140, duration=8.0)
            self.ctx.send_speech(msg)
            self.is_processing = False
            self.is_recording = False
            return

        if any(w in text_lower for w in ["switch ai backend", "toggle ai backend", "toggle ai", "switch backend"]):
            _, msg = self.ctx.ai.toggle_backend()
            self.ctx.send_emotion("excited", priority=140, duration=8.0)
            self.ctx.send_speech(msg)
            self.is_processing = False
            self.is_recording = False
            return

        # Fast-Path: Check for native OS Navigation, Browser, Command, & Telemetry actions
        try:
            from plugins.os_navigation.plugin import OSNavigationPlugin
            os_nav = OSNavigationPlugin()
            os_nav.ctx = self.ctx
            handled, reply, emotion = os_nav.handle_query(text)
            if handled:
                self.ctx.logger.info(f"OS Navigation handled query '{text}': {reply}")
                self.ctx.send_emotion(emotion, priority=140, duration=10.0)
                self.ctx.send_speech(reply)
                self.is_processing = False
                self.is_recording = False
                return
        except Exception as os_err:
            self.ctx.logger.debug(f"OS nav check skipped: {os_err}")

        # Keywords for camera/webcam vision (looking at the human, face, clothing, specs)
        camera_keywords = [
            "camera", "webcam", "face", "look at me", "see me", "wearing", "glasses",
            "specs", "spectacles", "hair", "holding", "my room", "shirt", "my view",
            "behind me", "am i", "my expression", "who am i", "looking at me", "how do i look"
        ]

        # Keywords for desktop screen vision (specifically asking to inspect/read the screen)
        screen_keywords = [
            "screen", "on my screen", "read my screen", "read the screen", "look at my screen",
            "look at screen", "describe my screen", "describe the screen", "explain this code",
            "read this code", "look at the code", "what's on my desktop", "what is on my desktop",
            "what's this", "what is this", "look at this", "read what is on", "tell me what is on"
        ]

        is_camera_query = any(k in text_lower for k in camera_keywords)
        is_screen_query = not is_camera_query and any(k in text_lower for k in screen_keywords)

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

        ZORO_PERSONA = (
            "You are Roronoa Zoro, the Pirate Hunter and master swordsman of the Straw Hat Pirates from One Piece. "
            "You are stoic, tough, loyal, blunt, and confident, addressing the user as Captain, Oi, or Nakama. "
            "You have an awful sense of direction (often confusing North and South), love napping, training with massive weights, drinking sake, and slicing obstacles with your three swords. "
            "Give a concise, badass, in-character response in 1 or 2 punchy sentences. Never break character."
        )

        # 1. Webcam Vision Path
        if is_camera_query:
            self.ctx.logger.info("Webcam visual query detected! Capturing camera frame...")
            self.ctx.send_speech("Looking at you... 👁️")
            self.ctx.send_emotion("curious", priority=150, duration=60.0)
            image_bytes = self._capture_webcam()
            if image_bytes:
                vision_prompt = (
                    f"The user asked while in front of their webcam: '{text}'.\n"
                    f"Persona: {ZORO_PERSONA}\n"
                    "Look through their camera, observe the visual scene, and give a sharp, in-character answer in 1 or 2 sentences."
                )
                self.ctx.ai.prompt_vision_async(
                    prompt=vision_prompt,
                    image_bytes=image_bytes,
                    callback=on_complete,
                    on_token=on_token,
                )
                return
            else:
                self.ctx.logger.warning("Webcam capture unavailable, trying screen or text fallback.")

        # 2. Desktop Screen Vision Path
        if is_screen_query:
            self.ctx.logger.info("Screen visual query detected! Capturing desktop frame...")
            self.ctx.send_speech("Reading screen... 🔍")
            self.ctx.send_emotion("curious", priority=150, duration=60.0)
            image_bytes = self._capture_screen()
            if image_bytes:
                vision_prompt = (
                    f"The user asked while looking at their desktop screen: '{text}'.\n"
                    f"Persona: {ZORO_PERSONA}\n"
                    "Look at their screen, analyze the open windows, code, or applications, and give an accurate, in-character answer in 1 or 2 sentences."
                )
                self.ctx.ai.prompt_vision_async(
                    prompt=vision_prompt,
                    image_bytes=image_bytes,
                    callback=on_complete,
                    on_token=on_token,
                )
                return
            else:
                self.ctx.logger.warning("Screen capture unavailable, falling back to text prompt.")

        # 3. General Conversational / Chat Path (Zoro persona)
        prompt_text = (
            f"The user said: '{text}'.\n"
            f"Persona: {ZORO_PERSONA}\n"
            "Give a complete, in-character response in 1 or 2 sentences."
        )

        self.ctx.ai.prompt_async(
            text=prompt_text,
            callback=on_complete,
            on_token=on_token,
            options=None,  # Unlimited token generation
        )

    def on_unload(self) -> None:
        self.ctx.logger.info("VoiceChatPlugin unloaded.")
