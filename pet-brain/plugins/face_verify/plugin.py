import os
import time
import threading
import random
from typing import Optional
import cv2
import numpy as np

from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class FaceVerifyPlugin(BasePlugin):
    """
    User Presence & Face Perception Plugin:
    - Periodically checks webcam for user presence using lightweight YuNet ONNX face detection (~2ms).
    - Greets user warmly when they sit down at their desk.
    - Strict privacy: Frames are processed purely in RAM and immediately released (zero disk storage).
    - Non-blocking: Webcam reads execute on background worker threads.
    """

    GREETINGS = [
        "Welcome back! Glad to see you! ✨",
        "I see you, friend! Let's get things done! 🌸",
        "Hello there! Ready for some productivity? 😊",
        "Yay, you're back! I was waiting for you! 💖",
    ]

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="FaceVerify",
            version="1.0.0",
            description="User presence and face perception plugin that detects when the user is at their desk and greets them.",
            subscriptions=["hotkey:face_scan"],
            tick_interval=20.0,
        )

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.is_scanning = False
        self.was_present = False
        self.last_greeting_time = 0.0
        self.cooldown_sec = 60.0  # At least 60 seconds between greetings
        self.detector = None
        self._init_detector()
        self.ctx.logger.info("FaceVerifyPlugin loaded! Ready for user presence perception.")

    def _init_detector(self):
        """Initialize YuNet ONNX face detector."""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(plugin_dir, "face_detection_yunet.onnx")
        if os.path.exists(model_path):
            try:
                self.detector = cv2.FaceDetectorYN.create(
                    model=model_path,
                    config="",
                    input_size=(320, 240),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000,
                )
                self.ctx.logger.info("YuNet ONNX Face detector initialized successfully!")
            except Exception as e:
                self.ctx.logger.warning(f"Could not load YuNet detector: {e}")
                self.detector = None

    def on_tick(self, elapsed: float = 0.0) -> None:
        """Periodic presence check every 20 seconds."""
        self._scan_async(is_manual=False)

    def on_event(self, event: IncomingEvent) -> None:
        """Manual face scan trigger."""
        if event.hotkey_id == "face_scan":
            self.ctx.logger.info("Manual face scan triggered!")
            self._scan_async(is_manual=True)

    def _scan_async(self, is_manual: bool = False):
        if self.is_scanning:
            return
        threading.Thread(target=self._scan_worker, args=(is_manual,), daemon=True).start()

    def _scan_worker(self, is_manual: bool):
        self.is_scanning = True
        try:
            # Capture 1 single frame from webcam
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.ctx.logger.debug("Webcam device /dev/video0 is currently busy or unavailable.")
                return

            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                return

            has_face = self._detect_face(frame)
            now = time.time()

            if has_face:
                self.ctx.logger.info("Face detected in webcam frame! User is present.")
                time_since_last_greeting = now - self.last_greeting_time

                # Greet if: manual trigger OR (user just returned and cooldown passed)
                if is_manual or (not self.was_present and time_since_last_greeting > self.cooldown_sec):
                    greeting = random.choice(self.GREETINGS)
                    self.ctx.send_emotion("happy", priority=140, duration=8.0)
                    self.ctx.send_speech(greeting)
                    self.last_greeting_time = now

                self.was_present = True
            else:
                self.ctx.logger.debug("No face detected in webcam frame.")
                if is_manual:
                    self.ctx.send_speech("(No face seen in camera)")
                self.was_present = False

        except Exception as e:
            self.ctx.logger.error(f"Error during face perception scan: {e}")
        finally:
            self.is_scanning = False

    def _detect_face(self, frame: np.ndarray) -> bool:
        """Perform fast ONNX face detection on image."""
        if self.detector is None:
            self._init_detector()
            if self.detector is None:
                return False

        try:
            h, w = frame.shape[:2]
            # Resize frame for ultra-fast ~1ms inference
            small = cv2.resize(frame, (320, 240))
            self.detector.setInputSize((320, 240))
            faces = self.detector.detect(small)
            return faces[1] is not None and len(faces[1]) > 0
        except Exception as e:
            self.ctx.logger.warning(f"Face detection inference failed: {e}")
            return False

    def on_unload(self) -> None:
        self.ctx.logger.info("FaceVerifyPlugin unloaded.")
