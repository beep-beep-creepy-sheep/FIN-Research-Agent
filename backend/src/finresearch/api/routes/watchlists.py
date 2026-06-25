from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from finresearch.api.dependencies import library_path
from finresearch.repositories.watchlists import WatchlistRepository


router = APIRouter()


class WatchlistItemCreate(BaseModel):
    symbol: str
    note: str | None = None


@router.get("")
def list_watchlist(db_path: Path = Depends(library_path)) -> list[dict[str, object]]:
    return WatchlistRepository(db_path).list()


@router.post("/items")
def add_watchlist_item(
    request: WatchlistItemCreate,
    db_path: Path = Depends(library_path),
) -> dict[str, str]:
    WatchlistRepository(db_path).add(request.symbol, request.note)
    return {"status": "ok", "symbol": request.symbol}

