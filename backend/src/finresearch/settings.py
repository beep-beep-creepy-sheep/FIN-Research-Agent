from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    documents_dir: Path
    raw_data_dir: Path
    reports_dir: Path
    llm_enabled: bool = False
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{data_dir / 'finresearch.sqlite'}",
        )
        return cls(
            database_url=database_url,
            data_dir=data_dir,
            documents_dir=Path(os.getenv("DOCUMENTS_DIR", data_dir / "documents")),
            raw_data_dir=Path(os.getenv("RAW_DATA_DIR", data_dir / "raw")),
            reports_dir=Path(os.getenv("REPORTS_DIR", data_dir / "reports")),
            llm_enabled=os.getenv("LLM_ENABLED", "false").lower() == "true",
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        )

    @property
    def sqlite_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.removeprefix("sqlite:///"))
        return self.data_dir / "finresearch.sqlite"


def get_settings() -> Settings:
    settings = Settings.from_env()
    for path in (settings.data_dir, settings.documents_dir, settings.raw_data_dir, settings.reports_dir):
        path.mkdir(parents=True, exist_ok=True)
    return settings

