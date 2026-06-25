from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str = "gpt-5.5"
    timeout_seconds: int = 90
    vector_store_id: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return cls(
            openai_api_key=key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
            timeout_seconds=int(os.getenv("FINRESEARCH_TIMEOUT_SECONDS", "90")),
            vector_store_id=os.getenv("OPENAI_VECTOR_STORE_ID", "").strip() or None,
        )


def default_library_path() -> Path:
    return Path(os.getenv("FINRESEARCH_LIBRARY", ".finresearch/library.sqlite"))
