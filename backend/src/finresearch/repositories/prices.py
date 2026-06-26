from __future__ import annotations

from sqlalchemy import select

from app.financial_store import infer_exchange
from app.models import PriceRecord
from finresearch.database.models import Company, Price
from finresearch.database.session import session_scope
from finresearch.metrics.context import PricePoint


class PriceRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def upsert_many(self, prices: list[PriceRecord]) -> int:
        if not prices:
            return 0
        with session_scope() as session:
            for price in prices:
                company = session.scalar(select(Company).where(Company.symbol == price.symbol))
                if company is None:
                    company = Company(
                        symbol=price.symbol,
                        exchange=infer_exchange(price.symbol),
                        company_name=price.symbol,
                        currency="CNY",
                    )
                    session.add(company)
                    session.flush()
                saved = session.scalar(
                    select(Price).where(
                        Price.symbol == price.symbol,
                        Price.trade_date == price.trade_date,
                        Price.adjustment_type == price.adjustment_type,
                        Price.data_source == price.data_source,
                    )
                )
                if saved is None:
                    saved = Price(
                        symbol=price.symbol,
                        trade_date=price.trade_date,
                        adjustment_type=price.adjustment_type,
                        data_source=price.data_source,
                    )
                    session.add(saved)
                saved.company_id = company.id
                saved.open = price.open
                saved.high = price.high
                saved.low = price.low
                saved.close = price.close
                saved.volume = price.volume
                saved.amount = price.amount
                saved.retrieved_at = price.retrieved_at
        return len(prices)

    def list_by_symbol(self, symbol: str, *, limit: int = 260) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(Price)
                .where(Price.symbol == symbol)
                .order_by(Price.trade_date.desc())
                .limit(limit)
            ).all()
            return [_price_dict(row) for row in rows]

    def price_series(
        self,
        symbol: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        adjustment_type: str | None = None,
        limit: int = 1000,
    ) -> list[PricePoint]:
        with session_scope() as session:
            statement = select(Price).where(Price.symbol == symbol)
            if start_date:
                statement = statement.where(Price.trade_date >= start_date)
            if end_date:
                statement = statement.where(Price.trade_date <= end_date)
            if adjustment_type:
                statement = statement.where(Price.adjustment_type == adjustment_type)
            rows = session.scalars(
                statement.order_by(Price.trade_date.asc()).limit(limit)
            ).all()
            points: list[PricePoint] = []
            for row in rows:
                if row.close is None:
                    continue
                points.append(
                    PricePoint(
                        id=row.id,
                        symbol=row.symbol,
                        trade_date=row.trade_date,
                        close=float(row.close),
                        adjustment_type=row.adjustment_type,
                        data_source=row.data_source,
                    )
                )
        return points


def _price_dict(price: Price) -> dict[str, object]:
    return {
        "id": price.id,
        "company_id": price.company_id,
        "symbol": price.symbol,
        "trade_date": price.trade_date,
        "open": price.open,
        "high": price.high,
        "low": price.low,
        "close": price.close,
        "volume": price.volume,
        "amount": price.amount,
        "adjustment_type": price.adjustment_type,
        "data_source": price.data_source,
        "retrieved_at": price.retrieved_at,
    }
