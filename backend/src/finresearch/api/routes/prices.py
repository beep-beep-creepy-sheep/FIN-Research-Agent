from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from finresearch.api.dependencies import library_path
from finresearch.repositories.prices import PriceRepository


router = APIRouter()


@router.get("/{symbol}/prices")
def get_prices(
    symbol: str,
    limit: int = 260,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return PriceRepository(db_path).list_by_symbol(symbol, limit=limit)

