from __future__ import annotations

from pathlib import Path

from finresearch.repositories.documents import DocumentRepository


class DocumentSearchService:
    def __init__(self, library_path: Path) -> None:
        self.repository = DocumentRepository(library_path)

    def search(self, query: str, limit: int = 8) -> list[dict[str, object]]:
        return [snippet.model_dump() for snippet in self.repository.search(query, limit=limit)]

