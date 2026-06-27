from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.services.job_service import JobService


router = APIRouter()


class JobCreate(BaseModel):
    job_type: str = "sync_company"
    symbol: str | None = None
    years: int = 5
    market: str = "CN"
    source_ids: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    filing_id: int | None = None


@router.post("")
def create_job(request: JobCreate, db_path: Path = Depends(library_path)) -> dict[str, object]:
    if request.job_type == "sync_company":
        if not request.symbol:
            raise HTTPException(status_code=400, detail="symbol_required")
        return JobService(db_path).create_sync_job(request.symbol, request.years)
    if request.job_type == "market_snapshot":
        return JobService(db_path).create_market_snapshot_job(request.market)
    if request.job_type == "sync_official_filings":
        if not request.symbol:
            raise HTTPException(status_code=400, detail="symbol_required")
        return JobService(db_path).create_official_filing_sync_job(
            request.symbol,
            source_ids=request.source_ids,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    if request.job_type in {"download_filing", "parse_filing", "reparse_document"}:
        if request.filing_id is None:
            raise HTTPException(status_code=400, detail="filing_id_required")
        return JobService(db_path).create_filing_job(request.job_type, request.filing_id)
    raise HTTPException(status_code=400, detail="unsupported_job_type")


@router.get("/{job_id}")
def get_job(job_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    job = JobService(db_path).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job
