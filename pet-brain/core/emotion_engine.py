import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pet_pb2


# Standard 16-state emotion catalog
VALID_EMOTIONS: Set[str] = {
    "idle",
    "happy",
    "sad",
    "angry",
    "startled",
    "curious",
    "thinking",
    "sleeping",
    "excited",
    "confused",
    "love",
    "bored",
    "proud",
    "embarrassed",
    "scared",
    "playful",
}

# Standard default priority hierarchy (0 = lowest, 255 = highest)
DEFAULT_PRIORITIES: Dict[str, int] = {
    "idle": 0,
    "bored": 20,
    "sleeping": 30,
    "happy": 50,
    "playful": 60,
    "curious": 80,
    "thinking": 100,
    "confused": 110,
    "excited": 120,
    "proud": 130,
    "embarrassed": 140,
    "sad": 150,
    "angry": 160,
    "love": 170,
    "scared": 190,
    "startled": 200,
}


@dataclass
class ActiveEmotion:
    emotion_id: str
    priority: int
    duration: Optional[float]  # Duration in seconds. None = indefinite until cleared
    start_time: float
    source: str


class EmotionEngine:
    """
    16-state priority machine managing emotion transitions, decay timers, and IPC dispatch.
    Resolves multi-plugin emotion conflicts and smoothly returns to lower-priority states or 'idle'.
    """

    def __init__(self, ipc_server: Any, default_emotion: str = "idle"):
        self.ipc = ipc_server
        self.default_emotion = default_emotion if default_emotion in VALID_EMOTIONS else "idle"
        self.current_emotion = self.default_emotion
        self.logger = logging.getLogger("EmotionEngine")
        
        # Active emotion requests: { (emotion_id, source): ActiveEmotion }
        self.active_emotions: Dict[Tuple[str, str], ActiveEmotion] = {}

    def request_emotion(
        self,
        emotion_id: str,
        priority: Optional[int] = None,
        duration: Optional[float] = 3.0,
        source: str = "default",
    ) -> bool:
        """
        Request a new emotion state.
        
        :param emotion_id: One of the 16 valid emotions
        :param priority: Priority value (0-255). If None, uses default emotion priority
        :param duration: Time in seconds before decaying. None for persistent/indefinite
        :param source: Identifier of the requesting plugin/subsystem
        :return: True if emotion is valid and was recorded
        """
        emotion_norm = emotion_id.lower().strip()
        if emotion_norm not in VALID_EMOTIONS:
            self.logger.warning(f"Unknown emotion requested: '{emotion_id}'. Falling back to 'curious'.")
            emotion_norm = "curious"

        eff_priority = priority if priority is not None else DEFAULT_PRIORITIES.get(emotion_norm, 50)
        
        entry = ActiveEmotion(
            emotion_id=emotion_norm,
            priority=eff_priority,
            duration=duration,
            start_time=time.time(),
            source=source,
        )

        self.active_emotions[(emotion_norm, source)] = entry
        self._resolve_and_dispatch()
        return True

    def clear_emotion(self, emotion_id: Optional[str] = None, source: Optional[str] = None):
        """
        Manually cancel an active emotion request.
        """
        keys_to_remove = []
        for (e_id, s_id) in self.active_emotions.keys():
            if (emotion_id is None or e_id == emotion_id) and (source is None or s_id == source):
                keys_to_remove.append((e_id, s_id))

        for k in keys_to_remove:
            del self.active_emotions[k]

        self._resolve_and_dispatch()

    def tick(self, dt: float) -> None:
        """
        Update decay timers, purge expired emotions, and transition state when necessary.
        """
        now = time.time()
        expired_keys = []

        for key, active in self.active_emotions.items():
            if active.duration is not None and (now - active.start_time) >= active.duration:
                expired_keys.append(key)

        if expired_keys:
            for k in expired_keys:
                del self.active_emotions[k]
            self._resolve_and_dispatch()

    def _resolve_and_dispatch(self) -> None:
        """
        Find the highest-priority active emotion and dispatch to Rust if changed.
        """
        highest_emotion = self.default_emotion
        highest_priority = -1
        latest_start = 0.0

        for active in self.active_emotions.values():
            if active.priority > highest_priority or (active.priority == highest_priority and active.start_time > latest_start):
                highest_priority = active.priority
                highest_emotion = active.emotion_id
                latest_start = active.start_time

        # If highest emotion changed, dispatch IPC command to Rust shell
        if highest_emotion != self.current_emotion:
            old_emotion = self.current_emotion
            self.current_emotion = highest_emotion
            self.logger.info(
                f"State Transition: '{old_emotion}' -> '{highest_emotion}' (Priority: {highest_priority})"
            )

            msg = pet_pb2.PetMessage()
            msg.emotion_command.emotion_id = highest_emotion
            msg.emotion_command.priority = max(0, highest_priority)
            try:
                self.ipc.send_message(msg)
            except Exception as e:
                self.logger.error(f"Failed to dispatch EmotionCommand to Rust: {e}")

    def get_current_emotion(self) -> str:
        return self.current_emotion
