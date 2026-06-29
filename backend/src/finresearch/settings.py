from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


SECRET_FIELD_HINTS = ("key", "secret", "token", "password", "cookie", "credential")
SAFE_ENVIRONMENTS = {"development", "test", "production"}
SAFE_OFFICIAL_SOURCE_MODES = {"disabled", "fixture", "live"}
SAFE_LLM_PROVIDERS = {"ollama", "openai"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    documents_dir: Path
    raw_data_dir: Path
    reports_dir: Path
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
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
        app_env = os.getenv("APP_ENV", "development").strip().lower() or "development"
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{data_dir / 'finresearch.sqlite'}",
        )
        official_mode = os.getenv("OFFICIAL_SOURCE_MODE")
        if official_mode is None:
            official_mode = "disabled" if app_env == "production" else "fixture"
        return cls(
            app_env=app_env,
            database_url=database_url,
            data_dir=data_dir,
            documents_dir=Path(os.getenv("DOCUMENTS_DIR", data_dir / "documents")),
            raw_data_dir=Path(os.getenv("RAW_DATA_DIR", data_dir / "raw")),
            reports_dir=Path(os.getenv("REPORTS_DIR", data_dir / "reports")),
            api_host=os.getenv("API_HOST", "127.0.0.1").strip() or "127.0.0.1",
            api_port=int(os.getenv("API_PORT", "8000")),
            cors_origins=_csv_tuple(
                os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
            ),
            llm_enabled=_env_bool("LLM_ENABLED", False),
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            ollama_connect_timeout_seconds=float(os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "2")),
            ollama_generate_timeout_seconds=float(os.getenv("OLLAMA_GENERATE_TIMEOUT_SECONDS", "45")),
            ollama_keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "10m"),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
            agent_reach_enabled=_env_bool("AGENT_REACH_ENABLED", False),
            exa_enabled=_env_bool("EXA_ENABLED", False),
            official_sources_enabled=_env_bool("OFFICIAL_SOURCES_ENABLED", True),
            official_source_mode=official_mode.strip().lower(),
            allow_fixture_official_sources=_env_bool("ALLOW_FIXTURE_OFFICIAL_SOURCES", False),
            run_live_source_tests=_env_bool("RUN_LIVE_SOURCE_TESTS", False),
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

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.app_env not in SAFE_ENVIRONMENTS:
            errors.append("APP_ENV must be development, test, or production")
        if self.official_source_mode not in SAFE_OFFICIAL_SOURCE_MODES:
            errors.append("OFFICIAL_SOURCE_MODE must be disabled, fixture, or live")
        if self.llm_provider not in SAFE_LLM_PROVIDERS:
            errors.append("LLM_PROVIDER must be ollama or openai")
        if self.api_port < 1 or self.api_port > 65535:
            errors.append("API_PORT must be between 1 and 65535")
        if any(origin == "*" for origin in self.cors_origins):
            errors.append("CORS_ORIGINS must not include '*'")
        if self.llm_enabled and self.llm_provider == "openai" and not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required when LLM_PROVIDER=openai and LLM_ENABLED=true")
        parsed = urlparse(self.database_url)
        if not (self.database_url.startswith("sqlite:///") or parsed.scheme.startswith("postgresql")):
            errors.append("DATABASE_URL must be sqlite:///... or postgresql(+psycopg)://...")
        if self.app_env == "production":
            if self.database_url.startswith("sqlite:///"):
                errors.append("Production APP_ENV requires PostgreSQL DATABASE_URL")
            if self.official_source_mode != "disabled" and not self.run_live_source_tests:
                errors.append("Production official sources must stay disabled unless RUN_LIVE_SOURCE_TESTS=true")
        return errors

    def redacted_summary(self) -> dict[str, object]:
        return {
            "app_env": self.app_env,
            "database": _database_summary(self.database_url),
            "storage": {
                "data_dir_configured": bool(self.data_dir),
                "documents_dir_configured": bool(self.documents_dir),
                "raw_data_dir_configured": bool(self.raw_data_dir),
                "reports_dir_configured": bool(self.reports_dir),
            },
            "api": {
                "host": self.api_host,
                "port": self.api_port,
                "cors_origins": list(self.cors_origins),
            },
            "llm": {"enabled": self.llm_enabled, "provider": self.llm_provider},
            "external_network": {
                "agent_reach_enabled": self.agent_reach_enabled,
                "exa_enabled": self.exa_enabled,
                "official_sources_enabled": self.official_sources_enabled,
                "official_source_mode": self.official_source_mode,
                "run_live_source_tests": self.run_live_source_tests,
            },
            "secrets": {
                "openai_api_key": _redact_secret(self.openai_api_key),
            },
        }


def validate_settings(settings: Settings | None = None) -> dict[str, object]:
    selected = settings or Settings.from_env()
    errors = selected.validate()
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "summary": selected.redacted_summary(),
    }


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
    if "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules:
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


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _database_summary(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite:///"):
        return {"engine": "sqlite", "configured": True}
    parsed = urlparse(database_url)
    return {"engine": parsed.scheme or "unknown", "host_configured": bool(parsed.hostname)}


def _redact_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "[redacted]"
    return f"{value[:2]}...[redacted]...{value[-2:]}"
