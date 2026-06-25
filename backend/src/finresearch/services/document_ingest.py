from __future__ import annotations

from pathlib import Path

from app.models import DocumentMetadata

from finresearch.repositories.documents import DocumentRepository


class DocumentIngestService:
    def __init__(self, library_path: Path) -> None:
        self.repository = DocumentRepository(library_path)

    def ingest(self, path: Path, metadata: DocumentMetadata | None = None) -> int:
        return self.repository.ingest(path, metadata)

