from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from finresearch.database.models import DataQualityIssue
from finresearch.database.session import session_scope


class DataQualityRepository:
    def upsert_issue(
        self,
        *,
        issue_type: str,
        severity: str,
        entity_type: str,
        entity_id: str | None,
        symbol: str | None = None,
        source_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> int:
        now = datetime.now(UTC)
        with session_scope() as session:
            issue = session.scalar(
                select(DataQualityIssue).where(
                    DataQualityIssue.issue_type == issue_type,
                    DataQualityIssue.entity_type == entity_type,
                    DataQualityIssue.entity_id == entity_id,
                    DataQualityIssue.source_id == source_id,
                )
            )
            if issue is None:
                issue = DataQualityIssue(
                    issue_type=issue_type,
                    severity=severity,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    symbol=symbol,
                    source_id=source_id,
                    status="open",
                    details=details or {},
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(issue)
            else:
                issue.severity = severity
                issue.symbol = symbol
                issue.details = details or issue.details
                issue.last_seen_at = now
                if issue.status == "resolved":
                    issue.status = "open"
            session.flush()
            return int(issue.id)

    def summary(self) -> dict[str, object]:
        with session_scope() as session:
            rows = session.execute(
                select(
                    DataQualityIssue.status,
                    DataQualityIssue.severity,
                    DataQualityIssue.issue_type,
                    DataQualityIssue.source_id,
                    func.count(DataQualityIssue.id),
                ).group_by(
                    DataQualityIssue.status,
                    DataQualityIssue.severity,
                    DataQualityIssue.issue_type,
                    DataQualityIssue.source_id,
                )
            ).all()
        open_count = 0
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for status, severity, issue_type, source_id, count in rows:
            if status == "open":
                open_count += count
            by_severity[str(severity)] = by_severity.get(str(severity), 0) + count
            by_type[str(issue_type)] = by_type.get(str(issue_type), 0) + count
            by_source[str(source_id or "unknown")] = by_source.get(str(source_id or "unknown"), 0) + count
        return {
            "open_count": open_count,
            "by_severity": by_severity,
            "by_type": by_type,
            "by_source": by_source,
        }

    def list(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, object]]:
        with session_scope() as session:
            query = select(DataQualityIssue).order_by(DataQualityIssue.last_seen_at.desc()).limit(limit)
            if status:
                query = query.where(DataQualityIssue.status == status)
            rows = session.scalars(query).all()
            return [_issue_dict(row) for row in rows]

    def get(self, issue_id: int) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(DataQualityIssue, issue_id)
            return _issue_dict(row) if row else None


def _issue_dict(row: DataQualityIssue) -> dict[str, object]:
    return {
        "id": row.id,
        "issue_type": row.issue_type,
        "severity": row.severity,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "symbol": row.symbol,
        "source_id": row.source_id,
        "status": row.status,
        "details": row.details,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "resolution_note": row.resolution_note,
    }
