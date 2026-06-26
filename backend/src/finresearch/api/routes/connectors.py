from __future__ import annotations

from fastapi import APIRouter

from finresearch.services.external_research import ExternalResearchService


router = APIRouter()


@router.get("")
def list_connectors() -> list[dict[str, object]]:
    return ExternalResearchService().health()


@router.post("/health-check")
def health_check() -> list[dict[str, object]]:
    return ExternalResearchService().health(force=True)
