from __future__ import annotations

from sqlalchemy import select

from finresearch.database.models import ResearchRun
from finresearch.database.session import session_scope


class ResearchRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def save(
        self,
        query: str,
        symbol: str | None,
        as_of_date: str | None,
        markdown: str,
        structured_result: dict[str, object] | None = None,
    ) -> int:
        with session_scope() as session:
            run = ResearchRun(
                query=query,
                question=query,
                symbol=symbol,
                as_of_date=as_of_date,
                report_markdown=markdown,
                result_markdown=markdown,
                structured_result=structured_result,
                status="completed",
            )
            session.add(run)
            session.flush()
            return int(run.id)

    def list(self, limit: int = 20) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(limit)
            ).all()
            return [
                {
                    "id": row.id,
                    "symbol": row.symbol,
                    "query": row.query,
                    "as_of_date": row.as_of_date,
                    "status": row.status,
                    "report_markdown": row.report_markdown,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
