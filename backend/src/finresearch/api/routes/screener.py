from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from finresearch.services.screener import ScreenQuery, ScreenerService


router = APIRouter()


class ScreenerRequest(BaseModel):
    q: str | None = None
    industry: str | None = None
    min_revenue: float | None = None
    min_net_margin: float | None = None
    min_roe: float | None = None
    max_liability_ratio: float | None = None
    sort_by: str = "revenue"
    sort_direction: str = "desc"
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


@router.post("/query")
def query_screener(request: ScreenerRequest) -> dict[str, object]:
    try:
        return ScreenerService().query(ScreenQuery(**request.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
