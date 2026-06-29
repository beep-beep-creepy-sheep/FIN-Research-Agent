from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from finresearch import __version__
from finresearch.data_sources.official_registry import OfficialSourceRegistry
from finresearch.database.session import build_engine, database_url
from finresearch.repositories.jobs import JobRepository
from finresearch.settings import get_settings, validate_settings


router = APIRouter()


@router.get("/status")
def system_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "checked_at": datetime.now(UTC).isoformat(),
        "version": __version__,
        "config": validate_settings(settings),
        "database": _database_status(),
        "storage": _storage_status(),
        "official_sources": _official_source_status(),
        "worker": _worker_status(),
    }


@router.get("/config-check")
def config_check(response: Response) -> dict[str, object]:
    result = validate_settings()
    if result["status"] != "passed":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


def readiness() -> tuple[int, dict[str, object]]:
    settings_result = validate_settings()
    checks = {
        "config": settings_result,
        "database": _database_status(),
        "storage": _storage_status(),
    }
    ready = all(
        item.get("status") == "ok" or item.get("status") == "passed"
        for item in checks.values()
        if isinstance(item, dict)
    )
    return (
        status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        {
            "status": "ready" if ready else "not_ready",
            "checked_at": datetime.now(UTC).isoformat(),
            "checks": checks,
        },
    )


def version_payload() -> dict[str, object]:
    return {
        "name": "finresearch",
        "version": __version__,
        "stage": "stage_8_production_security_release",
    }


def _database_status() -> dict[str, object]:
    try:
        engine = build_engine(database_url())
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "code": "database_unavailable", "error_type": type(exc).__name__}


def _storage_status() -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, dict[str, object]] = {}
    for name, path in {
        "data_dir": settings.data_dir,
        "documents_dir": settings.documents_dir,
        "raw_data_dir": settings.raw_data_dir,
        "reports_dir": settings.reports_dir,
    }.items():
        checks[name] = {"configured": True, "exists": path.exists(), "writable": _is_writable(path)}
    ok = all(item["exists"] and item["writable"] for item in checks.values())
    return {"status": "ok" if ok else "error", "paths": checks}


def _official_source_status() -> list[dict[str, object]]:
    settings = get_settings()
    return [
        {
            "source_id": definition.source_id,
            "source_tier": definition.source_tier,
            "enabled": settings.official_sources_enabled and settings.official_source_mode != "disabled",
            "mode": settings.official_source_mode,
        }
        for definition in OfficialSourceRegistry().list_definitions()
    ]


def _worker_status() -> dict[str, object]:
    try:
        queued = JobRepository().list_queued(limit=20)
    except Exception as exc:
        return {"status": "unknown", "code": "jobs_unavailable", "error_type": type(exc).__name__}
    return {"status": "ok", "queued_or_stale_count": len(queued)}


def _is_writable(path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".finresearch-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
