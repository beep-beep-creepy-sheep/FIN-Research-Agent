from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import inspect, select, text

from finresearch.database.models import Citation, ResearchRun
from finresearch.database.session import session_scope


class ResearchRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with session_scope() as session:
            bind = session.get_bind()
            columns = {column["name"] for column in inspect(bind).get_columns("research_runs")}
            additions = {
                "job_id": "INTEGER",
                "error_message": "TEXT",
                "completed_at": "TIMESTAMP" if bind.dialect.name != "sqlite" else "DATETIME",
            }
            for name, definition in additions.items():
                if name not in columns:
                    session.execute(text(f"ALTER TABLE research_runs ADD COLUMN {name} {definition}"))

    def create_pending(
        self,
        *,
        query: str,
        symbol: str,
        as_of_date: str | None = None,
    ) -> int:
        with session_scope() as session:
            run = ResearchRun(
                query=query,
                question=query,
                symbol=symbol,
                as_of_date=as_of_date,
                status="queued",
            )
            session.add(run)
            session.flush()
            return int(run.id)

    def attach_job(self, run_id: int, job_id: int) -> None:
        with session_scope() as session:
            run = session.get(ResearchRun, run_id)
            if run is not None:
                run.job_id = job_id

    def mark_running(self, run_id: int) -> None:
        with session_scope() as session:
            run = session.get(ResearchRun, run_id)
            if run is not None:
                run.status = "running"

    def mark_failed(self, run_id: int, error_message: str) -> None:
        with session_scope() as session:
            run = session.get(ResearchRun, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = error_message
                run.completed_at = datetime.now(UTC)

    def save(
        self,
        query: str,
        symbol: str | None,
        as_of_date: str | None,
        markdown: str,
        structured_result: dict[str, object] | None = None,
        run_id: int | None = None,
        citations: list[dict[str, object]] | None = None,
    ) -> int:
        with session_scope() as session:
            run = session.get(ResearchRun, run_id) if run_id is not None else None
            if run is None:
                run = ResearchRun(query=query, question=query, symbol=symbol, as_of_date=as_of_date)
                session.add(run)
            run.report_markdown = markdown
            run.result_markdown = markdown
            run.structured_result = structured_result
            run.status = "completed"
            run.error_message = None
            run.completed_at = datetime.now(UTC)
            session.flush()
            for item in citations or []:
                source_url = str(item.get("source_url") or item.get("url") or "")
                if not _is_formal_url(source_url):
                    continue
                session.add(
                    Citation(
                        research_run_id=run.id,
                        claim=str(item.get("claim") or item.get("title") or "external source"),
                        source_url=source_url,
                        document_id=item.get("document_id"),
                        page_number=item.get("page_number"),
                        support_status=str(item.get("support_status") or "unverified"),
                    )
                )
            return int(run.id)

    def get(self, run_id: int) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(ResearchRun, run_id)
            if row is None:
                return None
            citations = session.scalars(
                select(Citation).where(Citation.research_run_id == run_id).order_by(Citation.id)
            ).all()
            data = _run_dict(row)
            data["citations"] = [_citation_dict(citation) for citation in citations]
            return data

    def list(self, limit: int = 20) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(limit)
            ).all()
            return [
                _run_dict(row)
                for row in rows
            ]


def _run_dict(row: ResearchRun) -> dict[str, object]:
    return {
        "id": row.id,
        "job_id": row.job_id,
        "symbol": row.symbol,
        "query": row.query,
        "as_of_date": row.as_of_date,
        "status": row.status,
        "report_markdown": row.report_markdown,
        "structured_result": row.structured_result,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _citation_dict(row: Citation) -> dict[str, object]:
    return {
        "id": row.id,
        "research_run_id": row.research_run_id,
        "claim": row.claim,
        "source_url": row.source_url,
        "document_id": row.document_id,
        "page_number": row.page_number,
        "support_status": row.support_status,
    }


def _is_formal_url(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if lowered.startswith(("agent-reach://", "exa://", "generated://")):
        return False
    return lowered.startswith(("http://", "https://", "file://"))
