from __future__ import annotations

from pathlib import Path
from shutil import copyfileobj

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.repositories.documents import DocumentRepository
from finresearch.settings import get_settings
from app.models import DocumentMetadata
from finresearch.services.document_search import DocumentSearchService


router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 8


@router.get("")
def list_documents(db_path: Path = Depends(library_path)) -> list[dict[str, object]]:
    return DocumentRepository(db_path).list()


@router.get("/{document_id}")
def get_document(document_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    document = DocumentRepository(db_path).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "document_not_found"})
    return document


@router.get("/{document_id}/chunks")
def get_document_chunks(document_id: int, db_path: Path = Depends(library_path)) -> list[dict[str, object]]:
    return DocumentRepository(db_path).chunks(document_id)


@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    issuer: str | None = Form(default=None),
    report_period: str | None = Form(default=None),
    publication_date: str | None = Form(default=None),
    db_path: Path = Depends(library_path),
) -> dict[str, object]:
    settings = get_settings()
    upload_dir = settings.documents_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(file.filename or "document")
    destination = upload_dir / filename
    with destination.open("wb") as handle:
        copyfileobj(file.file, handle)
    metadata = DocumentMetadata(
        title=Path(filename).stem,
        source_path=str(destination),
        source_type=destination.suffix.lower().removeprefix(".") or "file",
        issuer=issuer or None,
        report_period=report_period or None,
        publication_date=publication_date or None,
    )
    document_id = DocumentRepository(db_path).ingest(destination, metadata)
    return {"id": document_id, "title": metadata.title, "filename": filename}


@router.post("/search")
def search_documents(
    request: SearchRequest,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return DocumentSearchService(db_path).search(request.query, request.limit)


def _safe_filename(filename: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in filename)
    return cleaned.strip("._") or "document"
