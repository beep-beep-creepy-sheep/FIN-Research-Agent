from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.repositories.filings import FilingRepository
from finresearch.services.job_service import JobService


router = APIRouter()


class FilingSyncRequest(BaseModel):
    source_ids: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    download: bool = True
    parse: bool = True


@router.post("/companies/{symbol}/filings/sync")
def create_filing_sync_job(
    symbol: str,
    request: FilingSyncRequest,
    db_path: Path = Depends(library_path),
) -> dict[str, object]:
    return JobService(db_path).create_official_filing_sync_job(
        symbol,
        source_ids=request.source_ids,
        start_date=request.start_date,
        end_date=request.end_date,
        download=request.download,
        parse=request.parse,
    )


@router.get("/companies/{symbol}/filings")
def list_company_filings(
    symbol: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, object]]:
    return FilingRepository().list(symbol, limit=limit, offset=offset)


@router.get("/filings/{filing_id}")
def get_filing(filing_id: int) -> dict[str, object]:
    filing = FilingRepository().get(filing_id)
    if filing is None:
        raise HTTPException(status_code=404, detail={"code": "filing_not_found"})
    return filing


@router.post("/filings/{filing_id}/download")
def create_filing_download_job(filing_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    return JobService(db_path).create_filing_job("download_filing", filing_id)


@router.post("/filings/{filing_id}/parse")
def create_filing_parse_job(filing_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    return JobService(db_path).create_filing_job("parse_filing", filing_id)


@router.post("/filings/{filing_id}/retry")
def create_filing_retry_job(filing_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    return JobService(db_path).create_filing_job("retry_filing", filing_id)
