from __future__ import annotations

from pathlib import Path

from sqlalchemy import or_, select

from app.document_store import chunk_text, hash_file, read_document_text, tokenize
from app.models import DocumentMetadata, EvidenceSnippet
from finresearch.database.models import Document, DocumentChunk
from finresearch.database.session import session_scope


class DocumentRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def ingest(self, path: Path, metadata: DocumentMetadata | None = None) -> int:
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        metadata = metadata or DocumentMetadata.from_path(path)
        text = read_document_text(path)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError(f"No extractable text found in {path}")

        source_path = str(path.resolve())
        digest = hash_file(path)
        with session_scope() as session:
            existing = session.scalar(
                select(Document).where(
                    or_(Document.source_path == source_path, Document.file_hash == digest)
                )
            )
            if existing is not None:
                session.delete(existing)
                session.flush()
            document = Document(
                title=metadata.title,
                source_path=source_path,
                local_path=source_path,
                source_type=metadata.source_type,
                issuer=metadata.issuer,
                report_period=metadata.report_period,
                publication_date=metadata.publication_date,
                currency=metadata.currency,
                unit=metadata.unit,
                url=metadata.url,
                source_url=metadata.url,
                file_hash=digest,
                document_type=metadata.source_type,
                metadata_json=metadata.model_dump(),
            )
            session.add(document)
            session.flush()
            for index, (chunk, start, end) in enumerate(chunks):
                session.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=index,
                        text=chunk,
                        search_vector=" ".join(tokenize(chunk)),
                        start_char=start,
                        end_char=end,
                    )
                )
            session.flush()
            return int(document.id)

    def search(self, query: str, *, limit: int = 8) -> list[EvidenceSnippet]:
        terms = tokenize(query)
        if not terms:
            return []
        with session_scope() as session:
            chunks = session.scalars(select(DocumentChunk).join(Document)).all()
            snippets: list[EvidenceSnippet] = []
            for chunk in chunks:
                document = chunk.document
                score = _score(terms, chunk.search_vector or chunk.text, document.title)
                if score <= 0:
                    continue
                snippets.append(
                    EvidenceSnippet(
                        document_id=int(document.id),
                        chunk_id=int(chunk.chunk_index),
                        title=document.title,
                        source_path=document.source_path or document.local_path or "",
                        text=chunk.text,
                        score=score,
                        issuer=document.issuer,
                        report_period=document.report_period,
                        publication_date=document.publication_date,
                        url=document.url or document.source_url,
                    )
                )
        snippets.sort(key=lambda item: item.score, reverse=True)
        return snippets[:limit]

    def list(self) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(select(Document).order_by(Document.id)).all()
            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "source_path": row.source_path,
                    "source_type": row.source_type,
                    "issuer": row.issuer,
                    "report_period": row.report_period,
                    "publication_date": row.publication_date,
                    "file_hash": row.file_hash,
                    "chunks": len(row.chunks),
                }
                for row in rows
            ]


def _score(terms: list[str], token_text: str, title: str) -> float:
    haystack = token_text.lower()
    title_lower = title.lower()
    score = 0.0
    for term in terms:
        occurrences = haystack.count(term)
        if occurrences:
            score += 1 + min(occurrences, 8) * 0.25
        if term in title_lower:
            score += 0.75
    return score
