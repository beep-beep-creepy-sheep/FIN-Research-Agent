from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.repositories.documents import DocumentRepository
from finresearch.services.document_search import DocumentSearchService


router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 8


@router.get("")
def list_documents(db_path: Path = Depends(library_path)) -> list[dict[str, object]]:
    return DocumentRepository(db_path).list()


@router.post("/search")
def search_documents(
    request: SearchRequest,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return DocumentSearchService(db_path).search(request.query, request.limit)

