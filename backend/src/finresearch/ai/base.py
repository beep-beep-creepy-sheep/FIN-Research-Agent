from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str: ...


class DisabledLLMProvider:
    def generate(self, prompt: str) -> str:
        raise RuntimeError("LLM is disabled")

