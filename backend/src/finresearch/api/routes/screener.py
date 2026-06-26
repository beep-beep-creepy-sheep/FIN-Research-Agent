from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

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
    limit: int = 50


@router.post("/query")
def query_screener(request: ScreenerRequest) -> dict[str, object]:
    return ScreenerService().query(ScreenQuery(**request.model_dump()))
