from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from finresearch.services.valuation import PeerMetricsMatrixService, PeerSetService, ValuationLabService


router = APIRouter()


class PeerRequest(BaseModel):
    as_of_date: str | None = None
    manual_peers: list[str] = Field(default_factory=list)
    exclude_symbols: list[str] = Field(default_factory=list)
    min_peer_count: int = Field(default=3, ge=0, le=50)
    max_peer_count: int = Field(default=10, ge=1, le=50)


class PeerMetricsRequest(BaseModel):
    peer_symbols: list[str] | None = None
    metric_codes: list[str] | None = None
    as_of_date: str | None = None
    strict_as_of: bool = False
    period: str | None = None
    industry_pack: str = "auto"


class ValuationRequest(BaseModel):
    model_type: str = "relative_valuation"
    scenario: str = "base"
    as_of_date: str | None = None
    strict_as_of: bool = False
    assumptions: dict[str, object] = Field(default_factory=dict)
    peer_symbols: list[str] | None = None
    include_evidence: bool = True
    include_sensitivity: bool = True


@router.get("/companies/{symbol}/peers")
def get_peers(
    symbol: str,
    as_of_date: str | None = None,
    min_peer_count: int = 3,
    max_peer_count: int = 10,
) -> dict[str, object]:
    return _peers(
        symbol,
        PeerRequest(as_of_date=as_of_date, min_peer_count=min_peer_count, max_peer_count=max_peer_count),
    )


@router.post("/companies/{symbol}/peers")
def create_peers(symbol: str, request: PeerRequest) -> dict[str, object]:
    return _peers(symbol, request)


@router.get("/companies/{symbol}/peer-metrics")
def get_peer_metrics(
    symbol: str,
    as_of_date: str | None = None,
    strict_as_of: bool = False,
) -> dict[str, object]:
    return _peer_metrics(symbol, PeerMetricsRequest(as_of_date=as_of_date, strict_as_of=strict_as_of))


@router.post("/companies/{symbol}/peer-metrics")
def post_peer_metrics(symbol: str, request: PeerMetricsRequest) -> dict[str, object]:
    return _peer_metrics(symbol, request)


@router.get("/companies/{symbol}/valuation")
def get_valuation(
    symbol: str,
    model_type: str = "relative_valuation",
    scenario: str = "base",
    as_of_date: str | None = None,
    strict_as_of: bool = False,
    include_evidence: bool = True,
    include_sensitivity: bool = True,
) -> dict[str, object]:
    return _valuation(
        symbol,
        ValuationRequest(
            model_type=model_type,
            scenario=scenario,
            as_of_date=as_of_date,
            strict_as_of=strict_as_of,
            include_evidence=include_evidence,
            include_sensitivity=include_sensitivity,
        ),
    )


@router.post("/companies/{symbol}/valuation")
def post_valuation(symbol: str, request: ValuationRequest) -> dict[str, object]:
    return _valuation(symbol, request)


@router.get("/companies/{symbol}/valuation/runs")
def get_valuation_runs(symbol: str) -> list[dict[str, object]]:
    return ValuationLabService().runs(symbol)


@router.get("/valuation/runs/{run_id}")
def get_valuation_run(run_id: str) -> dict[str, object]:
    row = ValuationLabService().get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "valuation_run_not_found"})
    return row


def _peers(symbol: str, request: PeerRequest) -> dict[str, object]:
    try:
        return PeerSetService().build(
            symbol,
            as_of_date=request.as_of_date,
            manual_peers=request.manual_peers,
            exclude_symbols=request.exclude_symbols,
            min_peer_count=request.min_peer_count,
            max_peer_count=request.max_peer_count,
        ).to_dict()
    except ValueError as exc:
        raise _http_error(exc) from exc


def _peer_metrics(symbol: str, request: PeerMetricsRequest) -> dict[str, object]:
    try:
        return PeerMetricsMatrixService().build(
            symbol,
            peer_symbols=request.peer_symbols,
            metric_codes=request.metric_codes,
            as_of_date=request.as_of_date,
            strict_as_of=request.strict_as_of,
            industry_pack=request.industry_pack,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


def _valuation(symbol: str, request: ValuationRequest) -> dict[str, object]:
    try:
        return ValuationLabService().run(
            symbol,
            model_type=request.model_type,
            scenario=request.scenario,
            as_of_date=request.as_of_date,
            strict_as_of=request.strict_as_of,
            assumptions=request.assumptions,
            peer_symbols=request.peer_symbols,
            include_evidence=request.include_evidence,
            include_sensitivity=request.include_sensitivity,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


def _http_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code == "company_not_found":
        return HTTPException(status_code=404, detail={"code": code})
    return HTTPException(status_code=400, detail={"code": code})
