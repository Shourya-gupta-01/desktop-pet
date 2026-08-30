import base64
import json
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Dict, List, Optional, Tuple, Any

import httpx


class AIBridge:
    """
    Asynchronous and thread-pooled bridge for local Ollama LLM and Vision inference.
    Ensures long-running model generations never block the main IPC loop or UI animations.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        text_model: str = "qwen2.5vl:7b",
        vision_model: str = "qwen2.5vl:7b",
        max_workers: int = 4,
    ):
        self.base_url = base_url.rstrip("/")
        self.text_model = text_model
        self.vision_model = vision_model
        self.logger = logging.getLogger("AIBridge")
        
        # Dedicated thread pool for non-blocking asynchronous AI reasoning
        self.client = httpx.Client(timeout=120.0)
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AIWorker")

    def health_check(self) -> Tuple[bool, str, List[str]]:
        """
        Check if Ollama service is reachable and required models are downloaded.
        """
        try:
            resp = self.client.get(f"{self.base_url}/api/tags", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                
                # Check for recommended models
                missing = []
                if not any(self.text_model in m for m in models):
                    missing.append(self.text_model)
                if not any(self.vision_model in m for m in models):
                    missing.append(self.vision_model)

                if missing:
                    msg = f"Ollama is running, but model(s) missing: {', '.join(missing)}. Pull via 'ollama pull <model>'."
                    self.logger.warning(msg)
                    return True, msg, models
                
                self.logger.info(f"Ollama health-check passed! Found models: {models}")
                return True, "Ollama is healthy and ready.", models
            else:
                msg = f"Ollama returned HTTP {resp.status_code}"
                self.logger.error(msg)
                return False, msg, []
        except httpx.ConnectError:
            msg = "Could not connect to Ollama at http://localhost:11434. Is Ollama running?"
            self.logger.warning(msg)
            return False, msg, []
        except Exception as e:
            msg = f"Ollama health-check failed: {e}"
            self.logger.error(msg)
            return False, msg, []

    def prompt(
        self,
        text: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Synchronously prompt local LLM.
        If on_token is provided, streams tokens incrementally.
        """
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
                # Streaming mode
                full_response = []
                with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=120.0) as resp:
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
                # Non-streaming mode
                resp = self.client.post(f"{self.base_url}/api/generate", json=payload, timeout=120.0)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "").strip()

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
        """
        Asynchronously prompt LLM on a background thread. Returns a concurrent.futures.Future.
        When finished, invokes callback(full_text).
        """
        def _worker():
            result = self.prompt(text=text, system=system, model=model, options=options, on_token=on_token)
            if callback:
                try:
                    callback(result)
                except Exception as cb_err:
                    self.logger.error(f"Error in prompt_async callback: {cb_err}", exc_info=True)
            return result

        return self.executor.submit(_worker)

    def prompt_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        model: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Synchronously prompt multimodal vision model (e.g. LLaVA) with image bytes.
        """
        target_model = model or self.vision_model
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": target_model,
            "prompt": prompt,
            "images": [b64_image],
            "stream": on_token is not None,
        }

        try:
            if on_token:
                full_response = []
                with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload, timeout=60.0) as resp:
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
                resp = self.client.post(f"{self.base_url}/api/generate", json=payload, timeout=60.0)
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
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Future:
        """
        Asynchronously prompt multimodal vision model on a background thread.
        When finished, invokes callback(full_text).
        """
        def _worker():
            result = self.prompt_vision(prompt=prompt, image_bytes=image_bytes, model=model, on_token=on_token)
            if callback:
                try:
                    callback(result)
                except Exception as cb_err:
                    self.logger.error(f"Error in prompt_vision_async callback: {cb_err}", exc_info=True)
            return result

        return self.executor.submit(_worker)

    def shutdown(self):
        """Shut down the thread pool and HTTP client cleanly."""
        self.logger.info("Shutting down AIBridge worker threads...")
        self.executor.shutdown(wait=False)
        self.client.close()
