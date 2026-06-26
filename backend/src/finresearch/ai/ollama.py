from __future__ import annotations

import requests

from finresearch.settings import Settings


class OllamaProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.settings.ollama_base_url}/api/generate",
                json={
                    "model": self.settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": self.settings.ollama_keep_alive,
                },
                timeout=(
                    self.settings.ollama_connect_timeout_seconds,
                    self.settings.ollama_generate_timeout_seconds,
                ),
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RuntimeError("ollama_timeout") from exc
        except requests.ConnectionError as exc:
            raise RuntimeError("ollama_unavailable") from exc
        except requests.HTTPError as exc:
            message = str(exc)
            if "404" in message:
                raise RuntimeError(f"ollama_model_missing:{self.settings.ollama_model}") from exc
            raise RuntimeError(f"ollama_http_error:{message}") from exc
        return str(response.json().get("response", ""))

    def status(self) -> dict[str, object]:
        try:
            response = requests.get(
                f"{self.settings.ollama_base_url}/api/tags",
                timeout=(self.settings.ollama_connect_timeout_seconds, 5),
            )
            response.raise_for_status()
            models = [row.get("name") for row in response.json().get("models", [])]
            return {
                "available": True,
                "model": self.settings.ollama_model,
                "model_present": self.settings.ollama_model in models,
                "models": models,
            }
        except requests.Timeout:
            return {"available": False, "model": self.settings.ollama_model, "error_type": "ollama_timeout"}
        except requests.RequestException as exc:
            return {
                "available": False,
                "model": self.settings.ollama_model,
                "error_type": "ollama_unavailable",
                "error_message": str(exc),
            }

    def warmup(self) -> dict[str, object]:
        try:
            self.generate("请仅回复 OK")
            return {"ok": True, "model": self.settings.ollama_model}
        except RuntimeError as exc:
            return {"ok": False, "model": self.settings.ollama_model, "error": str(exc)}
