from __future__ import annotations

from sqlalchemy import select

from finresearch.database.models import Watchlist, WatchlistItem
from finresearch.database.session import session_scope


class WatchlistRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def add(self, symbol: str, note: str | None = None) -> None:
        with session_scope() as session:
            watchlist = session.scalar(select(Watchlist).where(Watchlist.name == "Default"))
            if watchlist is None:
                watchlist = Watchlist(name="Default")
                session.add(watchlist)
                session.flush()
            item = session.scalar(
                select(WatchlistItem).where(
                    WatchlistItem.watchlist_id == watchlist.id,
                    WatchlistItem.symbol == symbol,
                )
            )
            if item is None:
                item = WatchlistItem(watchlist_id=watchlist.id, symbol=symbol)
                session.add(item)
            item.note = note or item.note

    def list(self) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(select(WatchlistItem).order_by(WatchlistItem.symbol)).all()
            return [
                {
                    "symbol": row.symbol,
                    "note": row.note,
                    "added_at": row.added_at.isoformat() if row.added_at else None,
                }
                for row in rows
            ]
