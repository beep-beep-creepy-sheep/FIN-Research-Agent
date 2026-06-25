from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.services.research_service import ResearchService


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
    return ResearchService(db_path).create_structured_run(
        request.symbol,
        years=request.years,
        as_of_date=request.as_of_date,
    )


@router.get("")
def list_research_runs(db_path: Path = Depends(library_path)) -> list[dict[str, object]]:
    return ResearchService(db_path).list_runs()

