from __future__ import annotations

from finresearch.connectors.base import ConnectorHealth
from finresearch.database.models import ConnectorStatus
from finresearch.database.session import session_scope


class ConnectorStatusRepository:
    def save_health(self, health: ConnectorHealth, *, enabled: bool) -> None:
        with session_scope() as session:
            row = session.get(ConnectorStatus, health.name)
            if row is None:
                row = ConnectorStatus(connector=health.name)
                session.add(row)
            row.enabled = enabled
            row.status = health.status
            row.active_backend = health.active_backend
            row.last_error = health.last_error

    def list(self) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.query(ConnectorStatus).order_by(ConnectorStatus.connector).all()
            return [
                {
                    "connector": row.connector,
                    "enabled": row.enabled,
                    "status": row.status,
                    "active_backend": row.active_backend,
                    "last_checked_at": row.last_checked_at,
                    "last_error": row.last_error,
                }
                for row in rows
            ]
