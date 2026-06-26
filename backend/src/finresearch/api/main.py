from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finresearch.api.routes import (
    companies,
    connectors,
    documents,
    external_sources,
    financials,
    jobs,
    market,
    prices,
    research,
    watchlists,
)


app = FastAPI(title="Fin Research Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router, prefix="/v1/companies", tags=["companies"])
app.include_router(financials.router, prefix="/v1/companies", tags=["financials"])
app.include_router(prices.router, prefix="/v1/companies", tags=["prices"])
app.include_router(documents.router, prefix="/v1/documents", tags=["documents"])
app.include_router(research.router, prefix="/v1/research-runs", tags=["research"])
app.include_router(watchlists.router, prefix="/v1/watchlists", tags=["watchlists"])
app.include_router(jobs.router, prefix="/v1/jobs", tags=["jobs"])
app.include_router(market.router, prefix="/v1/market", tags=["market"])
app.include_router(connectors.router, prefix="/v1/connectors", tags=["connectors"])
app.include_router(external_sources.router, prefix="/v1/external-sources", tags=["external-sources"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
