from __future__ import annotations

import re
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from finresearch.api.routes import (
    companies,
    ai,
    analysis,
    connectors,
    data_quality,
    data_sources,
    documents,
    external_sources,
    filings,
    financials,
    jobs,
    market,
    portfolios,
    prices,
    reports,
    research,
    screener,
    system,
    valuation,
    watchlists,
)
from finresearch.settings import get_settings


app = FastAPI(
    title="Fin Research Agent API",
    version="0.1.0",
    description="Evidence-first local financial research API. Research use only; no broker or trading integration.",
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router, prefix="/v1/companies", tags=["companies"])
app.include_router(analysis.router, prefix="/v1", tags=["analysis"])
app.include_router(ai.router, prefix="/v1/ai", tags=["ai"])
app.include_router(financials.router, prefix="/v1/companies", tags=["financials"])
app.include_router(prices.router, prefix="/v1/companies", tags=["prices"])
app.include_router(documents.router, prefix="/v1/documents", tags=["documents"])
app.include_router(research.router, prefix="/v1/research-runs", tags=["research"])
app.include_router(watchlists.router, prefix="/v1/watchlists", tags=["watchlists"])
app.include_router(jobs.router, prefix="/v1/jobs", tags=["jobs"])
app.include_router(market.router, prefix="/v1/market", tags=["market"])
app.include_router(portfolios.router, prefix="/v1", tags=["portfolios"])
app.include_router(screener.router, prefix="/v1/screener", tags=["screener"])
app.include_router(screener.router, prefix="/v1/screens", tags=["screens"])
app.include_router(valuation.router, prefix="/v1", tags=["valuation"])
app.include_router(reports.router, prefix="/v1", tags=["reports"])
app.include_router(connectors.router, prefix="/v1/connectors", tags=["connectors"])
app.include_router(external_sources.router, prefix="/v1/external-sources", tags=["external-sources"])
app.include_router(data_sources.router, prefix="/v1/data-sources", tags=["data-sources"])
app.include_router(filings.router, prefix="/v1", tags=["filings"])
app.include_router(data_quality.router, prefix="/v1/data-quality", tags=["data-quality"])
app.include_router(system.router, prefix="/v1/system", tags=["system"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response) -> dict[str, object]:
    status_code, payload = system.readiness()
    response.status_code = status_code
    return payload


@app.get("/version")
def version() -> dict[str, object]:
    return system.version_payload()


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(request, exc.status_code, exc.detail),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "loc": [str(part) for part in error.get("loc", [])],
            "message": _sanitize_message(str(error.get("msg", "validation error"))),
            "type": str(error.get("type", "validation_error")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"code": "validation_error", "details": details},
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {"code": "internal_error", "message": type(exc).__name__},
        ),
    )


def _error_payload(request: Request, status_code: int, detail: object) -> dict[str, object]:
    code = "http_error"
    message = "Request failed"
    extra: dict[str, object] = {}
    if isinstance(detail, dict):
        code = str(detail.get("code") or code)
        message = str(detail.get("message") or code)
        extra = {str(key): value for key, value in detail.items() if key not in {"code", "message"}}
    elif isinstance(detail, str):
        code = detail or code
        message = detail or message
    error: dict[str, object] = {
        "code": _sanitize_message(code),
        "message": _sanitize_message(message),
        "status": status_code,
        "request_id": getattr(request.state, "request_id", None),
    }
    sanitized: dict[str, object] = {"error": error}
    if extra:
        error["details"] = _sanitize_object(extra)
    sanitized["detail"] = _sanitize_object(detail)
    return sanitized


def _sanitize_object(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _sanitize_object(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_object(item) for item in value]
    if isinstance(value, str):
        return _sanitize_message(value)
    return value


def _sanitize_message(value: str) -> str:
    redacted = re.sub(r"file://\S+", "[local_path_redacted]", value)
    redacted = re.sub(r"(?<!\w)/(?:Users|private|tmp|var|home|Volumes)/[^\s\"']+", "[local_path_redacted]", redacted)
    redacted = re.sub(r"[A-Za-z]:\\[^\s\"']+", "[local_path_redacted]", redacted)
    return redacted
