from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.services.job_service import JobService


router = APIRouter()


class JobCreate(BaseModel):
    job_type: str = "sync_company"
    symbol: str
    years: int = 5


@router.post("")
def create_job(request: JobCreate, db_path: Path = Depends(library_path)) -> dict[str, object]:
    if request.job_type != "sync_company":
        raise HTTPException(status_code=400, detail="unsupported_job_type")
    return JobService(db_path).create_sync_job(request.symbol, request.years)


@router.get("/{job_id}")
def get_job(job_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    job = JobService(db_path).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job_not_found")
    return job
