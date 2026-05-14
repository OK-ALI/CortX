from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class LLMAvailability:
    ollama_enabled: bool


@dataclass
class OllamaClient:
    base_url: str
    model: str
    timeout_seconds: int = 45
    keep_alive: str = "30m"

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.2,
        num_predict: int = 1024,
    ) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        if system:
            payload["system"] = system

        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        timeout = httpx.Timeout(self.timeout_seconds)

        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        text = str(data.get("response", "")).strip()
        if not text:
            raise RuntimeError("Ollama returned an empty response")
        return text

    def warm_model(self) -> bool:
        """Warm the model into memory and keep it resident for keep_alive duration."""
        payload = {
            "model": self.model,
            "prompt": "Reply with OK.",
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": 0.0, "num_predict": 2},
        }
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        timeout = httpx.Timeout(self.timeout_seconds)

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()
            return True
        except Exception:  # noqa: BLE001
            return False

    def unload_model(self) -> bool:
        """Request immediate model unload from Ollama to release memory."""
        payload = {
            "model": self.model,
            "prompt": "",
            "stream": False,
            "keep_alive": "0s",
            "options": {"num_predict": 0},
        }
        endpoint = f"{self.base_url.rstrip('/')}/api/generate"
        timeout = httpx.Timeout(self.timeout_seconds)

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()
            return True
        except Exception:  # noqa: BLE001
            return False


def create_ollama_client(
    base_url: str,
    model: str,
    timeout_seconds: int = 20,
    keep_alive: str = "30m",
) -> OllamaClient:
    return OllamaClient(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        keep_alive=keep_alive,
    )


def get_llm_availability(
    ollama_url: str,
    ollama_model: str | None = None,
) -> LLMAvailability:
    """Return local Ollama availability for pipeline decisions."""
    ollama_enabled = bool(ollama_url.strip())
    if ollama_enabled:
        try:
            endpoint = f"{ollama_url.rstrip('/')}/api/tags"
            response = httpx.get(endpoint, timeout=2.0)
            if response.status_code == 200:
                if not ollama_model:
                    ollama_enabled = True
                else:
                    data = response.json()
                    models = data.get("models", []) if isinstance(data, dict) else []
                    names = {str(item.get("name", "")) for item in models if isinstance(item, dict)}
                    ollama_enabled = ollama_model in names
            else:
                ollama_enabled = False
        except Exception:  # noqa: BLE001
            ollama_enabled = False

    return LLMAvailability(ollama_enabled=ollama_enabled)
