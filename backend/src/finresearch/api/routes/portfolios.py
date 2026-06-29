from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from finresearch.repositories.portfolios import PortfolioRepository
from finresearch.services.portfolio import (
    AlertsService,
    CalendarService,
    PortfolioAnalyticsService,
    PortfolioPerformanceService,
    PortfolioReportService,
    PortfolioRiskService,
    PortfolioService,
)


router = APIRouter()


class PortfolioPayload(BaseModel):
    name: str
    description: str | None = None
    base_currency: str = "CNY"
    portfolio_type: str = Field(default="watchlist", pattern="^(watchlist|research_portfolio|manual_holdings)$")


class PortfolioPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    base_currency: str | None = None
    portfolio_type: str | None = None


class HoldingPayload(BaseModel):
    symbol: str
    quantity: float | None = None
    cost_basis: float | None = None
    cost_currency: str | None = None
    position_date: str | None = None
    weight_override: float | None = None
    notes: str | None = None


class WatchItemPayload(BaseModel):
    symbol: str
    thesis: str | None = None
    interest_level: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class AlertRulePayload(BaseModel):
    symbol: str | None = None
    rule_type: str
    metric_code: str | None = None
    threshold: float | None = None
    direction: str | None = None
    enabled: bool = True
    severity: str = "medium"


class CalendarEventPayload(BaseModel):
    portfolio_id: int | None = None
    symbol: str | None = None
    event_type: str = "manual"
    title: str
    event_date: str
    source: str = "manual"
    filing_id: int | None = None
    report_run_id: int | None = None
    notes: str | None = None
    severity: str = "medium"


@router.get("/portfolios")
def list_portfolios() -> list[dict[str, object]]:
    return PortfolioService().list()


@router.post("/portfolios")
def create_portfolio(payload: PortfolioPayload) -> dict[str, object]:
    try:
        return PortfolioService().create(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": str(exc)}) from exc


@router.get("/portfolios/{portfolio_id}")
def get_portfolio(portfolio_id: int) -> dict[str, object]:
    row = PortfolioService().get(portfolio_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "portfolio_not_found"})
    return row


@router.patch("/portfolios/{portfolio_id}")
def update_portfolio(portfolio_id: int, payload: PortfolioPatch) -> dict[str, object]:
    row = PortfolioService().update(portfolio_id, payload.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "portfolio_not_found"})
    return row


@router.delete("/portfolios/{portfolio_id}")
def archive_portfolio(portfolio_id: int) -> dict[str, object]:
    if not PortfolioService().archive(portfolio_id):
        raise HTTPException(status_code=404, detail={"code": "portfolio_not_found"})
    return {"portfolio_id": portfolio_id, "archived": True}


@router.get("/portfolios/{portfolio_id}/holdings")
def list_holdings(
    portfolio_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, object]]:
    _require_portfolio(portfolio_id)
    return PortfolioRepository().holdings(portfolio_id, offset=offset, limit=limit)


@router.post("/portfolios/{portfolio_id}/holdings")
def add_holding(portfolio_id: int, payload: HoldingPayload) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    return PortfolioRepository().add_holding(portfolio_id, payload.model_dump())


@router.patch("/portfolios/{portfolio_id}/holdings/{holding_id}")
def update_holding(portfolio_id: int, holding_id: int, payload: HoldingPayload) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    row = PortfolioRepository().update_holding(portfolio_id, holding_id, payload.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "portfolio_holding_not_found"})
    return row


@router.delete("/portfolios/{portfolio_id}/holdings/{holding_id}")
def delete_holding(portfolio_id: int, holding_id: int) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    if not PortfolioRepository().delete_holding(portfolio_id, holding_id):
        raise HTTPException(status_code=404, detail={"code": "portfolio_holding_not_found"})
    return {"deleted": True}


@router.get("/portfolios/{portfolio_id}/watch-items")
def list_watch_items(
    portfolio_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, object]]:
    _require_portfolio(portfolio_id)
    return PortfolioRepository().watch_items(portfolio_id, offset=offset, limit=limit)


@router.post("/portfolios/{portfolio_id}/watch-items")
def add_watch_item(portfolio_id: int, payload: WatchItemPayload) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    return PortfolioRepository().add_watch_item(portfolio_id, payload.model_dump())


@router.patch("/portfolios/{portfolio_id}/watch-items/{item_id}")
def update_watch_item(portfolio_id: int, item_id: int, payload: WatchItemPayload) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    row = PortfolioRepository().update_watch_item(portfolio_id, item_id, payload.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "portfolio_watch_item_not_found"})
    return row


@router.delete("/portfolios/{portfolio_id}/watch-items/{item_id}")
def delete_watch_item(portfolio_id: int, item_id: int) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    if not PortfolioRepository().delete_watch_item(portfolio_id, item_id):
        raise HTTPException(status_code=404, detail={"code": "portfolio_watch_item_not_found"})
    return {"deleted": True}


@router.get("/portfolios/{portfolio_id}/summary")
def portfolio_summary(portfolio_id: int) -> dict[str, object]:
    return _service_result(lambda: PortfolioAnalyticsService().summary(portfolio_id))


@router.get("/portfolios/{portfolio_id}/exposure")
def portfolio_exposure(portfolio_id: int) -> dict[str, object]:
    return _service_result(lambda: PortfolioAnalyticsService().exposure(portfolio_id))


@router.get("/portfolios/{portfolio_id}/risk")
def portfolio_risk(portfolio_id: int) -> dict[str, object]:
    return _service_result(lambda: PortfolioRiskService().snapshot(portfolio_id))


@router.get("/portfolios/{portfolio_id}/performance")
def portfolio_performance(portfolio_id: int) -> dict[str, object]:
    return _service_result(lambda: PortfolioPerformanceService().performance(portfolio_id))


@router.get("/portfolios/{portfolio_id}/data-quality")
def portfolio_data_quality(portfolio_id: int) -> dict[str, object]:
    return _service_result(lambda: PortfolioAnalyticsService().data_quality(portfolio_id))


@router.get("/portfolios/{portfolio_id}/report")
def portfolio_report(portfolio_id: int) -> dict[str, object]:
    return _service_result(lambda: PortfolioReportService().build(portfolio_id))


@router.get("/portfolios/{portfolio_id}/alerts/rules")
def list_alert_rules(portfolio_id: int) -> list[dict[str, object]]:
    _require_portfolio(portfolio_id)
    return PortfolioRepository().alert_rules(portfolio_id)


@router.post("/portfolios/{portfolio_id}/alerts/rules")
def add_alert_rule(portfolio_id: int, payload: AlertRulePayload) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    return PortfolioRepository().add_alert_rule(portfolio_id, payload.model_dump())


@router.patch("/portfolios/{portfolio_id}/alerts/rules/{rule_id}")
def update_alert_rule(portfolio_id: int, rule_id: int, payload: AlertRulePayload) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    row = PortfolioRepository().update_alert_rule(portfolio_id, rule_id, payload.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "alert_rule_not_found"})
    return row


@router.delete("/portfolios/{portfolio_id}/alerts/rules/{rule_id}")
def delete_alert_rule(portfolio_id: int, rule_id: int) -> dict[str, object]:
    _require_portfolio(portfolio_id)
    if not PortfolioRepository().delete_alert_rule(portfolio_id, rule_id):
        raise HTTPException(status_code=404, detail={"code": "alert_rule_not_found"})
    return {"deleted": True}


@router.post("/portfolios/{portfolio_id}/alerts/evaluate")
def evaluate_alerts(portfolio_id: int) -> dict[str, object]:
    return _service_result(lambda: AlertsService().evaluate(portfolio_id))


@router.get("/portfolios/{portfolio_id}/alerts/events")
def list_alert_events(
    portfolio_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, object]]:
    _require_portfolio(portfolio_id)
    return PortfolioRepository().alert_events(portfolio_id, offset=offset, limit=limit)


@router.post("/portfolios/{portfolio_id}/alerts/events/{event_id}/acknowledge")
def acknowledge_alert_event(portfolio_id: int, event_id: int) -> dict[str, object]:
    row = PortfolioRepository().set_alert_event_status(portfolio_id, event_id, "acknowledged")
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "alert_event_not_found"})
    return row


@router.post("/portfolios/{portfolio_id}/alerts/events/{event_id}/dismiss")
def dismiss_alert_event(portfolio_id: int, event_id: int) -> dict[str, object]:
    row = PortfolioRepository().set_alert_event_status(portfolio_id, event_id, "dismissed")
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "alert_event_not_found"})
    return row


@router.get("/calendar/events")
def list_calendar_events(
    start_date: str | None = None,
    end_date: str | None = None,
    portfolio_id: int | None = None,
    symbol: str | None = None,
    severity: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    return CalendarService().list_events(
        start_date=start_date,
        end_date=end_date,
        portfolio_id=portfolio_id,
        symbol=symbol,
        severity=severity,
        offset=offset,
        limit=limit,
    )


@router.post("/calendar/events")
def add_calendar_event(payload: CalendarEventPayload) -> dict[str, object]:
    try:
        return CalendarService().create_event(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": str(exc)}) from exc


@router.patch("/calendar/events/{event_id}")
def update_calendar_event(event_id: int, payload: CalendarEventPayload) -> dict[str, object]:
    row = CalendarService().update_event(event_id, payload.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "calendar_event_not_found"})
    return row


@router.delete("/calendar/events/{event_id}")
def delete_calendar_event(event_id: int) -> dict[str, object]:
    if not CalendarService().delete_event(event_id):
        raise HTTPException(status_code=404, detail={"code": "calendar_event_not_found"})
    return {"deleted": True}


def _require_portfolio(portfolio_id: int) -> None:
    if PortfolioService().get(portfolio_id) is None:
        raise HTTPException(status_code=404, detail={"code": "portfolio_not_found"})


def _service_result(func):
    try:
        return func()
    except ValueError as exc:
        if str(exc) == "portfolio_not_found":
            raise HTTPException(status_code=404, detail={"code": "portfolio_not_found"}) from exc
        raise HTTPException(status_code=400, detail={"code": str(exc)}) from exc
