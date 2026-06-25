from __future__ import annotations

import requests

from finresearch.settings import Settings


class OllamaProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, prompt: str) -> str:
        response = requests.post(
            f"{self.settings.ollama_base_url}/api/generate",
            json={"model": self.settings.ollama_model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return str(response.json().get("response", ""))

