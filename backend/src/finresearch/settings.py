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
    ollama_connect_timeout_seconds: float = 2.0
    ollama_generate_timeout_seconds: float = 45.0
    ollama_keep_alive: str = "10m"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"
    agent_reach_enabled: bool = False
    exa_enabled: bool = False
    official_sources_enabled: bool = True
    official_source_mode: str = "fixture"
    allow_fixture_official_sources: bool = False
    run_live_source_tests: bool = False
    official_source_request_timeout_seconds: float = 10.0
    official_source_read_timeout_seconds: float = 30.0
    official_source_rate_limit_per_second: float = 0.5
    cn_stock_adjustment_type: str = "qfq"
    price_source_priority: tuple[str, ...] = (
        "local_prices",
        "akshare",
        "exchange",
    )

    @classmethod
    def from_env(cls) -> "Settings":
        load_local_env()
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{data_dir / 'finresearch.sqlite'}",
        )
        official_mode = os.getenv("OFFICIAL_SOURCE_MODE")
        if official_mode is None:
            official_mode = "disabled" if os.getenv("APP_ENV", "").lower() == "production" else "fixture"
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
            ollama_connect_timeout_seconds=float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "2")),
            ollama_generate_timeout_seconds=float(os.getenv("OLLAMA_GENERATE_TIMEOUT_SECONDS", "45")),
            ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "10m"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
            agent_reach_enabled=os.getenv("AGENT_REACH_ENABLED", "false").lower() == "true",
            exa_enabled=os.getenv("EXA_ENABLED", "false").lower() == "true",
            official_sources_enabled=os.getenv("OFFICIAL_SOURCES_ENABLED", "true").lower() == "true",
            official_source_mode=official_mode.strip().lower(),
            allow_fixture_official_sources=os.getenv("ALLOW_FIXTURE_OFFICIAL_SOURCES", "false").lower()
            == "true",
            run_live_source_tests=os.getenv("RUN_LIVE_SOURCE_TESTS", "false").lower() == "true",
            official_source_request_timeout_seconds=float(
                os.getenv("OFFICIAL_SOURCE_REQUEST_TIMEOUT_SECONDS", "10")
            ),
            official_source_read_timeout_seconds=float(
                os.getenv("OFFICIAL_SOURCE_READ_TIMEOUT_SECONDS", "30")
            ),
            official_source_rate_limit_per_second=float(
                os.getenv("OFFICIAL_SOURCE_RATE_LIMIT_PER_SECOND", "0.5")
            ),
            cn_stock_adjustment_type=os.getenv("CN_STOCK_ADJUSTMENT_TYPE", "qfq").strip().lower() or "qfq",
            price_source_priority=tuple(
                item.strip()
                for item in os.getenv(
                    "PRICE_SOURCE_PRIORITY",
                    "local_prices,akshare,exchange",
                ).split(",")
                if item.strip()
            ),
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


def database_url_from_env() -> str:
    load_local_env()
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    return os.getenv("DATABASE_URL", f"sqlite:///{data_dir / 'finresearch.sqlite'}")


def load_local_env() -> None:
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    for path in (Path("backend/.env"), Path(".env")):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
