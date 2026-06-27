from __future__ import annotations

from fastapi import APIRouter, HTTPException

from finresearch.data_sources.official_registry import OfficialSourceRegistry, source_coverage_matrix


router = APIRouter()


@router.get("")
def list_data_sources() -> list[dict[str, object]]:
    return source_coverage_matrix()


@router.get("/{source_id}")
def get_data_source(source_id: str) -> dict[str, object]:
    definition = OfficialSourceRegistry().get_definition(source_id)
    if definition is None:
        raise HTTPException(status_code=404, detail={"code": "source_not_found"})
    return {
        "source_id": definition.source_id,
        "source_name": definition.source_name,
        "source_tier": definition.source_tier,
        "supported_markets": list(definition.supported_markets),
        "supported_exchanges": list(definition.supported_exchanges),
        "allowed_domains": list(definition.allowed_domains),
        "rate_limit_policy": definition.rate_limit_policy,
    }


@router.get("/{source_id}/health")
def get_data_source_health(source_id: str) -> dict[str, object]:
    registry = OfficialSourceRegistry()
    if registry.get_definition(source_id) is None:
        raise HTTPException(status_code=404, detail={"code": "source_not_found"})
    return registry.get_adapter(source_id).health_check().__dict__
