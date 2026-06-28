from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from finresearch.services.screener import ScreenQuery, ScreenerService


router = APIRouter()


class ScreenerRequest(BaseModel):
    q: str | None = None
    market: str | None = None
    exchange: str | None = None
    industry: str | None = None
    sector: str | None = None
    listing_board: str | None = None
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    min_liquidity: float | None = None
    min_revenue: float | None = None
    min_revenue_growth: float | None = None
    min_net_profit_growth: float | None = None
    min_net_margin: float | None = None
    min_roe: float | None = None
    min_roic: float | None = None
    min_gross_margin: float | None = None
    min_fcf_yield: float | None = None
    max_debt_to_assets: float | None = None
    max_net_debt_to_ebitda: float | None = None
    min_cash_conversion: float | None = None
    min_current_ratio: float | None = None
    max_pe_ttm: float | None = None
    max_ev_ebitda: float | None = None
    min_relative_percentile: float | None = None
    valuation_scenario_status: str | None = None
    max_volatility: float | None = None
    max_drawdown: float | None = None
    max_beta: float | None = None
    min_data_quality_score: float | None = None
    official_source_coverage: str | None = None
    missing_filing: bool | None = None
    source_conflict: bool | None = None
    insufficient_data: bool | None = None
    min_overall_research_quality_score: float | None = None
    min_growth_score: float | None = None
    min_profitability_score: float | None = None
    min_cash_flow_quality_score: float | None = None
    min_balance_sheet_score: float | None = None
    min_earnings_quality_score: float | None = None
    industry_pack: str | None = None
    max_risk_flag_count: int | None = None
    max_liability_ratio: float | None = None
    include_missing: bool = False
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


class PresetRequest(BaseModel):
    name: str
    filters: dict[str, object] = Field(default_factory=dict)


@router.get("/presets")
def list_presets() -> list[dict[str, object]]:
    return ScreenerService().list_presets()


@router.post("/presets")
def save_preset(request: PresetRequest) -> dict[str, object]:
    try:
        return ScreenerService().save_preset(request.name, request.filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export")
def export_screener(
    fmt: str = "json",
    q: str | None = None,
    industry: str | None = None,
    sort_by: str = "revenue",
    sort_direction: str = "desc",
    limit: int = 50,
) -> Response:
    try:
        media_type, body = ScreenerService().export(
            ScreenQuery(q=q, industry=industry, sort_by=sort_by, sort_direction=sort_direction, limit=limit),
            fmt=fmt,
        )
        return Response(content=body, media_type=media_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
