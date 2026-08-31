import os
import base64
import json
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Dict, List, Optional, Tuple, Any

import httpx


def load_dotenv_file(filepath: str) -> Dict[str, str]:
    """Simple parser for .env key=value files without third-party dependencies."""
    env_dict = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("\"'")
                        env_dict[k] = v
        except Exception:
            pass
    return env_dict


class AIBridge:
    """
    Unified Multi-Backend AI Bridge supporting both:
    1. Local Inference: Ollama (Qwen2.5-VL 7B) - 100% Offline
    2. Cloud Inference: Google Gemini API (gemini-2.0-flash / gemini-1.5-flash) - Sub-second (<1.5s) Vision
    
    Supports 1-click and dynamic runtime backend switching, token streaming, and automatic offline fallback.
    """

    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        text_model: str = "qwen2.5vl:7b",
        vision_model: str = "qwen2.5vl:7b",
        gemini_model: str = "gemini-2.0-flash",
        backend: str = "local",
        max_workers: int = 4,
    ):
        self.logger = logging.getLogger("AIBridge")
        self.ollama_base_url = base_url.rstrip("/")
        self.text_model = text_model
        self.vision_model = vision_model
        self.gemini_model = gemini_model
        self.backend = backend.lower()
        self.gemini_api_key = ""

        # Load environment variables & .env configs
        self.reload_config()

        # Dedicated connection-pooled HTTP client
        self.client = httpx.Client(timeout=httpx.Timeout(180.0, connect=15.0))
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AIWorker")

    def reload_config(self) -> None:
        """Reload configuration and API keys from .env files or environment."""
        env_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"),
            os.path.expanduser("~/.config/desktop-pet/.env"),
        ]

        merged_env = {}
        for candidate in env_candidates:
            if os.path.exists(candidate):
                merged_env.update(load_dotenv_file(candidate))

        # Check process environment override first, then .env, then current in-memory value
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY") or merged_env.get("GEMINI_API_KEY") or self.gemini_api_key or ""
        self.gemini_model = os.environ.get("GEMINI_MODEL") or merged_env.get("GEMINI_MODEL") or self.gemini_model or "gemini-2.0-flash"
        
        configured_backend = os.environ.get("AI_BACKEND") or merged_env.get("AI_BACKEND") or self.backend
        if configured_backend:
            self.backend = configured_backend.lower()

        if self.gemini_api_key and self.backend == "gemini":
            self.logger.info(f"AIBridge initialized with Cloud Backend: Google Gemini ({self.gemini_model})")
        else:
            self.logger.info(f"AIBridge initialized with Local Backend: Ollama ({self.vision_model})")

    def set_backend(self, backend: str) -> Tuple[bool, str]:
        """
        Dynamically switch the active AI backend at runtime ('local' or 'gemini').
        Returns (success, status_message).
        """
        target = backend.strip().lower()
        if target in ["gemini", "cloud", "google"]:
            self.reload_config()
            if not self.gemini_api_key:
                msg = "Cannot switch to Gemini: GEMINI_API_KEY is not set. Add it to pet-brain/.env or environment."
                self.logger.warning(msg)
                return False, msg
            self.backend = "gemini"
            msg = f"Switched AI Backend to: Google Gemini ({self.gemini_model}) 🚀"
            self.logger.info(msg)
            return True, msg

        elif target in ["local", "ollama", "qwen", "offline"]:
            self.backend = "local"
            msg = f"Switched AI Backend to: Local Ollama ({self.vision_model}) 💻"
            self.logger.info(msg)
            return True, msg

        return False, f"Unknown AI backend: '{backend}'. Choose 'local' or 'gemini'."

    def toggle_backend(self) -> Tuple[str, str]:
        """Toggle between Local and Gemini backends with 1 click/command."""
        if self.backend == "gemini":
            _, msg = self.set_backend("local")
            return self.backend, msg
        else:
            success, msg = self.set_backend("gemini")
            if not success:
                return self.backend, msg
            return self.backend, msg

    def health_check(self) -> Tuple[bool, str, List[str]]:
        """Check status of active AI backend."""
        if self.backend == "gemini":
            if not self.gemini_api_key:
                return False, "Gemini API Key missing.", []
            return True, f"Google Gemini ({self.gemini_model}) ready.", [self.gemini_model]

        try:
            resp = self.client.get(f"{self.ollama_base_url}/api/tags", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return True, "Ollama is healthy and ready.", models
            return False, f"Ollama returned HTTP {resp.status_code}", []
        except Exception as e:
            return False, f"Ollama health-check failed: {e}", []

    # -------------------------------------------------------------
    # TEXT COMPLETIONS (Local Ollama vs Gemini Flash)
    # -------------------------------------------------------------
    def prompt(
        self,
        text: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Prompt LLM using active backend (Gemini or Local Ollama)."""
        if self.backend == "gemini" and self.gemini_api_key:
            try:
                return self._prompt_gemini(text=text, system=system, model=model, on_token=on_token)
            except Exception as e:
                self.logger.warning(f"Gemini prompt failed ({e}), falling back to local Ollama...")

        return self._prompt_ollama(text=text, system=system, model=model, options=options, on_token=on_token)

    def _prompt_gemini(
        self,
        text: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Call Google Gemini REST API."""
        target_model = model or self.gemini_model
        url = f"{self.GEMINI_BASE_URL}/models/{target_model}:generateContent?key={self.gemini_api_key}"

        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"System Instruction: {system}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        contents.append({"role": "user", "parts": [{"text": text}]})

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 300},
        }

        resp = self.client.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                full_text = parts[0].get("text", "").strip()
                if on_token and full_text:
                    on_token(full_text)
                return full_text
        return ""

    def _prompt_ollama(
        self,
        text: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Call local Ollama generate API."""
        target_model = model or self.text_model
        payload = {
            "model": target_model,
            "prompt": text,
            "stream": on_token is not None,
        }
        if system:
            payload["system"] = system
        if options:
            payload["options"] = options

        try:
            if on_token:
                full_response = []
                with self.client.stream("POST", f"{self.ollama_base_url}/api/generate", json=payload, timeout=180.0) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                full_response.append(token)
                                on_token(token)
                            if data.get("done", False):
                                break
                return "".join(full_response)
            else:
                resp = self.client.post(f"{self.ollama_base_url}/api/generate", json=payload, timeout=180.0)
                resp.raise_for_status()
                return resp.json().get("response", "").strip()

        except Exception as e:
            self.logger.error(f"Error during Ollama prompt generation ({target_model}): {e}")
            return f"[AI Error: {e}]"

    def prompt_async(
        self,
        text: str,
        callback: Optional[Callable[[str], None]] = None,
        system: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Future:
        """Asynchronously prompt LLM on background thread pool."""
        def _worker():
            result = self.prompt(text=text, system=system, model=model, options=options, on_token=on_token)
            if callback:
                try:
                    callback(result)
                except Exception as cb_err:
                    self.logger.error(f"Error in prompt_async callback: {cb_err}", exc_info=True)
            return result

        return self.executor.submit(_worker)

    # -------------------------------------------------------------
    # MULTIMODAL VISION INFERENCE (Local Qwen2.5-VL vs Gemini Flash)
    # -------------------------------------------------------------
    def prompt_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Prompt multimodal vision model with image bytes."""
        if self.backend == "gemini" and self.gemini_api_key:
            try:
                return self._prompt_vision_gemini(prompt=prompt, image_bytes=image_bytes, model=model, on_token=on_token)
            except Exception as e:
                self.logger.warning(f"Gemini vision failed ({e}), falling back to local Qwen2.5-VL...")

        return self._prompt_vision_ollama(prompt=prompt, image_bytes=image_bytes, model=model, options=options, on_token=on_token)

    def _prompt_vision_gemini(
        self,
        prompt: str,
        image_bytes: bytes,
        model: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Send image & prompt to Google Gemini 2.0 Flash REST API."""
        target_model = model or self.gemini_model
        url = f"{self.GEMINI_BASE_URL}/models/{target_model}:generateContent?key={self.gemini_api_key}"

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 300,
            },
        }

        resp = self.client.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                full_text = parts[0].get("text", "").strip()
                if on_token and full_text:
                    on_token(full_text)
                return full_text
        return ""

    def _prompt_vision_ollama(
        self,
        prompt: str,
        image_bytes: bytes,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Call local Ollama multimodal model (Qwen2.5-VL)."""
        target_model = model or self.vision_model
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": target_model,
            "prompt": prompt,
            "images": [b64_image],
            "stream": on_token is not None,
        }
        if options:
            payload["options"] = options

        try:
            if on_token:
                full_response = []
                with self.client.stream("POST", f"{self.ollama_base_url}/api/generate", json=payload, timeout=180.0) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            full_response.append(token)
                            on_token(token)
                            if chunk.get("done", False):
                                break
                return "".join(full_response)
            else:
                resp = self.client.post(f"{self.ollama_base_url}/api/generate", json=payload, timeout=180.0)
                resp.raise_for_status()
                return resp.json().get("response", "").strip()

        except Exception as e:
            self.logger.error(f"Error during vision prompt generation ({target_model}): {e}")
            return f"[Vision AI Error: {e}]"

    def prompt_vision_async(
        self,
        prompt: str,
        image_bytes: bytes,
        callback: Optional[Callable[[str], None]] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Future:
        """Asynchronously prompt multimodal vision model on background thread pool."""
        def _worker():
            result = self.prompt_vision(prompt=prompt, image_bytes=image_bytes, model=model, options=options, on_token=on_token)
            if callback:
                try:
                    callback(result)
                except Exception as cb_err:
                    self.logger.error(f"Error in prompt_vision_async callback: {cb_err}", exc_info=True)
            return result

        return self.executor.submit(_worker)

    def shutdown(self):
        """Clean shutdown of worker threads and HTTP connection pool."""
        self.logger.info("Shutting down AIBridge worker threads...")
        self.executor.shutdown(wait=False)
        self.client.close()
