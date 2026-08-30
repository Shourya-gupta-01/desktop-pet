import logging
import os
import threading
from typing import Optional, Callable, Any
import numpy as np


class STTEngine:
    """
    Offline Speech-To-Text Engine using faster-whisper.
    Provides fast, local voice transcription on CPU/GPU without internet access.
    """

    def __init__(
        self,
        model_size: str = "tiny.en",
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.logger = logging.getLogger("STTEngine")
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model_loaded(self):
        """Lazy load the Whisper model on first invocation with automatic CPU fallback."""
        if self._model is not None:
            return

        with self._lock:
            if self._model is not None:
                return
            try:
                from faster_whisper import WhisperModel
                self.logger.info(f"Loading faster-whisper model '{self.model_size}' on {self.device} ({self.compute_type})...")
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                self.logger.info("faster-whisper model loaded successfully!")
            except Exception as e:
                if self.device != "cpu":
                    self.logger.warning(f"Failed to load on {self.device} ({e}). Falling back to CPU...")
                    from faster_whisper import WhisperModel
                    self.device = "cpu"
                    self.compute_type = "int8"
                    self._model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8",
                    )
                    self.logger.info("faster-whisper model loaded on CPU successfully!")
                else:
                    self.logger.error(f"Failed to load faster-whisper model: {e}")
                    raise e

    def transcribe_audio_array(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe a 1D float32 numpy audio array.
        """
        self._ensure_model_loaded()
        if audio.ndim > 1:
            audio = audio.mean(axis=1)  # Convert to mono
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Skip transcription if buffer is purely silent
        rms = np.sqrt(np.mean(audio**2))
        if rms < 0.005 or len(audio) < sample_rate * 0.4:
            return ""

        segments, info = self._model.transcribe(audio, beam_size=1, language="en")
        text = " ".join([seg.text.strip() for seg in segments]).strip()
        self.logger.info(f"Transcribed ({info.language}, prob={info.language_probability:.2f}): '{text}'")
        return text

    def record_and_transcribe(
        self,
        max_duration_sec: float = 8.0,
        silence_timeout_sec: float = 1.3,
        initial_silence_timeout_sec: float = 3.5,
        sample_rate: int = 16000,
        on_speech_started: Optional[Callable[[], None]] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """
        Record audio with dynamic voice activity detection:
        - Gives you up to 3.5s to start speaking.
        - Once speaking starts, supports speaking for up to 8.0s.
        - Allows natural pauses up to 1.3s before automatically stopping.
        """
        def _worker():
            try:
                import sounddevice as sd
                import time

                self.logger.info("Listening with smart voice activity detection...")
                block_size = int(sample_rate * 0.1)  # 100ms chunks
                audio_chunks = []
                has_speech_started = False
                silence_start_time = None
                start_time = time.time()

                with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=block_size) as stream:
                    while True:
                        chunk, _ = stream.read(block_size)
                        flat_chunk = chunk.flatten()
                        audio_chunks.append(flat_chunk)

                        rms = np.sqrt(np.mean(flat_chunk**2))
                        now = time.time()
                        elapsed = now - start_time

                        if rms > 0.012:  # Speech threshold
                            if not has_speech_started:
                                has_speech_started = True
                                self.logger.info("User started speaking...")
                                if on_speech_started:
                                    try:
                                        on_speech_started()
                                    except Exception:
                                        pass
                            silence_start_time = None

                        elif has_speech_started:
                            # User was speaking, now paused/stopped
                            if silence_start_time is None:
                                silence_start_time = now
                            elif now - silence_start_time >= silence_timeout_sec:
                                self.logger.info(f"User finished speaking ({elapsed:.1f}s total). Stopping recording.")
                                break

                        else:
                            # User hasn't started speaking yet
                            if elapsed >= initial_silence_timeout_sec:
                                self.logger.info("No speech started within timeout.")
                                break

                        if elapsed >= max_duration_sec:
                            self.logger.info(f"Max recording duration reached ({max_duration_sec}s).")
                            break

                if not audio_chunks or not has_speech_started:
                    if callback:
                        callback("")
                    return ""

                full_audio = np.concatenate(audio_chunks)
                self.logger.info(f"Recorded {len(full_audio)/sample_rate:.2f}s of speech. Transcribing...")
                text = self.transcribe_audio_array(full_audio, sample_rate=sample_rate)
                if callback:
                    callback(text)
                return text

            except Exception as e:
                self.logger.error(f"Error during audio recording/transcription: {e}")
                if callback:
                    callback("")
                return ""

        if callback:
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            return None
        else:
            return _worker()

    # --- Push-To-Talk (Hold-To-Speak) Interface ---

    def start_push_to_talk(self, sample_rate: int = 16000) -> bool:
        """Start buffering audio when the user holds the push-to-talk shortcut."""
        import sounddevice as sd

        with self._lock:
            if getattr(self, "_ptt_recording", False):
                return False

            self._ptt_recording = True
            self._ptt_chunks = []
            self._ptt_sample_rate = sample_rate

            def _ptt_stream_worker():
                block_size = int(sample_rate * 0.1)
                try:
                    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=block_size) as stream:
                        while getattr(self, "_ptt_recording", False):
                            chunk, _ = stream.read(block_size)
                            self._ptt_chunks.append(chunk.flatten())
                except Exception as e:
                    self.logger.error(f"Error in PTT audio stream: {e}")

            self._ptt_thread = threading.Thread(target=_ptt_stream_worker, daemon=True)
            self._ptt_thread.start()
            self.logger.info("Push-to-talk recording started...")
            return True

    def stop_push_to_talk(self, callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """Stop buffering audio when the user releases the shortcut and transcribe."""
        with self._lock:
            if not getattr(self, "_ptt_recording", False):
                if callback:
                    callback("")
                return ""
            self._ptt_recording = False

        if hasattr(self, "_ptt_thread"):
            self._ptt_thread.join(timeout=1.0)

        def _transcribe_worker():
            chunks = getattr(self, "_ptt_chunks", [])
            sample_rate = getattr(self, "_ptt_sample_rate", 16000)
            if not chunks:
                if callback:
                    callback("")
                return ""

            full_audio = np.concatenate(chunks)
            self.logger.info(f"PTT complete ({len(full_audio)/sample_rate:.2f}s of audio). Transcribing...")
            text = self.transcribe_audio_array(full_audio, sample_rate=sample_rate)
            if callback:
                callback(text)
            return text

        if callback:
            t = threading.Thread(target=_transcribe_worker, daemon=True)
            t.start()
            return None
        else:
            return _transcribe_worker()
