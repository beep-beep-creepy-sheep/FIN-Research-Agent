from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from finresearch.services.external_research import ExternalResearchService


router = APIRouter()


class ExternalSearchRequest(BaseModel):
    query: str
    connectors: list[str] | None = None
    limit: int = 10


class ReadURLRequest(BaseModel):
    url: str
    connector: str = "direct_web"


@router.get("")
def list_external_sources(limit: int = 50, platform: str | None = None) -> list[dict[str, object]]:
    return ExternalResearchService().list_sources(limit=limit, platform=platform)


@router.post("/search")
def search_external_sources(request: ExternalSearchRequest) -> dict[str, object]:
    result = ExternalResearchService().search(
        request.query,
        connectors=request.connectors,
        limit=request.limit,
    )
    return result.__dict__


@router.post("/read")
def read_external_url(request: ReadURLRequest) -> dict[str, object]:
    return ExternalResearchService().read_url(request.url, request.connector)
