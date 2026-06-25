from __future__ import annotations

from sqlalchemy import select

from finresearch.connectors.base import ExternalItem
from finresearch.database.models import ExternalSource
from finresearch.database.session import session_scope


class ExternalSourceRepository:
    def upsert_many(self, items: list[ExternalItem]) -> int:
        for item in items:
            self.upsert(item)
        return len(items)

    def upsert(self, item: ExternalItem) -> int:
        with session_scope() as session:
            saved = session.scalar(
                select(ExternalSource).where(
                    ExternalSource.platform == item.platform,
                    ExternalSource.url == item.url,
                )
            )
            if saved is None:
                saved = ExternalSource(
                    connector=item.connector,
                    platform=item.platform,
                    url=item.url,
                    content_hash=item.content_hash,
                    fetched_at=item.fetched_at,
                )
                session.add(saved)
            saved.connector = item.connector
            saved.external_id = item.external_id
            saved.title = item.title
            saved.author = item.author
            saved.published_at = item.published_at
            saved.fetched_at = item.fetched_at
            saved.content = item.content
            saved.content_hash = item.content_hash
            saved.trust_level = item.trust_level
            saved.verification_status = item.verification_status
            saved.meta = item.metadata
            session.flush()
            return int(saved.id)

    def list(self, limit: int = 50, platform: str | None = None) -> list[dict[str, object]]:
        with session_scope() as session:
            statement = select(ExternalSource).order_by(ExternalSource.id.desc()).limit(limit)
            if platform:
                statement = (
                    select(ExternalSource)
                    .where(ExternalSource.platform == platform)
                    .order_by(ExternalSource.id.desc())
                    .limit(limit)
                )
            return [_source_dict(row) for row in session.scalars(statement).all()]


def _source_dict(source: ExternalSource) -> dict[str, object]:
    return {
        "id": source.id,
        "connector": source.connector,
        "platform": source.platform,
        "external_id": source.external_id,
        "title": source.title,
        "url": source.url,
        "author": source.author,
        "published_at": source.published_at,
        "fetched_at": source.fetched_at,
        "content": source.content,
        "content_hash": source.content_hash,
        "trust_level": source.trust_level,
        "verification_status": source.verification_status,
        "metadata": source.meta,
    }

