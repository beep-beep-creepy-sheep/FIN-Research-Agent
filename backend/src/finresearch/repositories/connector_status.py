from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect, text

from finresearch.connectors.base import ConnectorHealth
from finresearch.database.models import ConnectorStatus
from finresearch.database.session import session_scope


HEALTH_CACHE_SECONDS = 600
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_OPEN_SECONDS = 600


class ConnectorStatusRepository:
    def ensure_schema(self) -> None:
        with session_scope() as session:
            bind = session.get_bind()
            columns = {column["name"] for column in inspect(bind).get_columns("connector_status")}
            definitions = {
                "configured": "BOOLEAN DEFAULT FALSE",
                "available": "BOOLEAN DEFAULT FALSE",
                "requires_login": "BOOLEAN DEFAULT FALSE",
                "failure_count": "INTEGER DEFAULT 0",
                "retry_after": "VARCHAR(64)",
            }
            for name, definition in definitions.items():
                if name not in columns:
                    session.execute(text(f"ALTER TABLE connector_status ADD COLUMN {name} {definition}"))

    def save_health(self, health: ConnectorHealth, *, enabled: bool) -> None:
        self.ensure_schema()
        with session_scope() as session:
            row = session.get(ConnectorStatus, health.name)
            if row is None:
                row = ConnectorStatus(connector=health.name)
                session.add(row)
            row.enabled = enabled
            row.configured = health.configured
            row.available = health.available
            row.requires_login = health.requires_login
            row.status = health.status
            row.active_backend = health.active_backend
            row.last_error = health.last_error
            row.last_checked_at = _now_iso()
            if health.status != "circuit_open":
                row.failure_count = health.failure_count
                row.retry_after = health.retry_after

    def get(self, connector: str) -> dict[str, object] | None:
        self.ensure_schema()
        with session_scope() as session:
            row = session.get(ConnectorStatus, connector)
            return _row_dict(row) if row else None

    def get_cached(self, connector: str, *, max_age_seconds: int = HEALTH_CACHE_SECONDS) -> dict[str, object] | None:
        row = self.get(connector)
        if row is None:
            return None
        retry_after = _parse_time(row.get("retry_after"))
        if row.get("status") == "circuit_open" and retry_after and retry_after > datetime.now(UTC):
            return row
        checked_at = _parse_time(row.get("last_checked_at"))
        if checked_at is None:
            return None
        if datetime.now(UTC) - checked_at <= timedelta(seconds=max_age_seconds):
            return row
        return None

    def record_success(self, connector: str) -> None:
        self.ensure_schema()
        with session_scope() as session:
            row = session.get(ConnectorStatus, connector)
            if row is None:
                return
            row.failure_count = 0
            row.retry_after = None
            if row.status == "circuit_open":
                row.status = "available"
                row.available = True
            row.last_error = None

    def record_failure(self, connector: str, error: str) -> dict[str, object] | None:
        self.ensure_schema()
        with session_scope() as session:
            row = session.get(ConnectorStatus, connector)
            if row is None:
                row = ConnectorStatus(connector=connector, enabled=True)
                session.add(row)
            row.failure_count = int(row.failure_count or 0) + 1
            row.last_error = error
            row.last_checked_at = _now_iso()
            if row.failure_count >= CIRCUIT_FAILURE_THRESHOLD:
                row.status = "circuit_open"
                row.available = False
                row.retry_after = (datetime.now(UTC) + timedelta(seconds=CIRCUIT_OPEN_SECONDS)).isoformat()
            session.flush()
            return _row_dict(row)

    def list(self) -> list[dict[str, object]]:
        self.ensure_schema()
        with session_scope() as session:
            rows = session.query(ConnectorStatus).order_by(ConnectorStatus.connector).all()
            return [_row_dict(row) for row in rows]


def _row_dict(row: ConnectorStatus) -> dict[str, object]:
    return {
        "name": row.connector,
        "connector": row.connector,
        "enabled": bool(row.enabled),
        "configured": bool(getattr(row, "configured", False)),
        "available": bool(getattr(row, "available", False)),
        "requires_login": bool(getattr(row, "requires_login", False)),
        "status": row.status,
        "active_backend": row.active_backend,
        "last_checked_at": row.last_checked_at,
        "last_error": row.last_error,
        "failure_count": int(getattr(row, "failure_count", 0) or 0),
        "retry_after": getattr(row, "retry_after", None),
    }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
