from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.services.research_service import ResearchService
from finresearch.services.job_service import JobService


router = APIRouter()


class ResearchCreate(BaseModel):
    symbol: str
    years: int = 5
    as_of_date: str | None = None


@router.post("")
def create_research_run(
    request: ResearchCreate,
    db_path: Path = Depends(library_path),
) -> dict[str, object]:
    pending = ResearchService(db_path).create_background_run(
        request.symbol.upper(),
        years=request.years,
        as_of_date=request.as_of_date,
    )
    job = JobService(db_path).create_research_job(
        research_run_id=int(pending["research_run_id"]),
        symbol=request.symbol,
        years=request.years,
        as_of_date=request.as_of_date,
    )
    ResearchService(db_path).research_repo.attach_job(int(pending["research_run_id"]), int(job["id"]))
    return {
        **pending,
        "job_id": job["id"],
        "job_status": job["status"],
    }


@router.get("")
def list_research_runs(db_path: Path = Depends(library_path)) -> list[dict[str, object]]:
    return ResearchService(db_path).list_runs()


@router.get("/{run_id}")
def get_research_run(run_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    run = ResearchService(db_path).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="research_run_not_found")
    return run


@router.get("/{run_id}/status")
def get_research_run_status(run_id: int, db_path: Path = Depends(library_path)) -> dict[str, object]:
    run = ResearchService(db_path).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="research_run_not_found")
    return {
        "id": run["id"],
        "job_id": run.get("job_id"),
        "status": run.get("status"),
        "error_message": run.get("error_message"),
        "completed_at": run.get("completed_at"),
    }
