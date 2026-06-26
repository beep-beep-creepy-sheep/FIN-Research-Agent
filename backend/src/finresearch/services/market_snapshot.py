from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import fmean, median

from sqlalchemy import select

from finresearch.database.models import Company, Price
from finresearch.database.session import session_scope
from finresearch.repositories.market import MarketRepository, MetricDefinitionRepository


@dataclass(frozen=True)
class MarketSnapshotResult:
    snapshot: dict[str, object]
    breadth: dict[str, object] | None
    sectors: list[dict[str, object]]
    movers: dict[str, list[dict[str, object]]]
    warnings: list[str]


class MarketSnapshotService:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.market_repo = MarketRepository()
        self.metric_repo = MetricDefinitionRepository()

    def generate(self, market: str = "CN") -> MarketSnapshotResult:
        now = datetime.now(UTC)
        as_of = now.isoformat()
        snapshot_date = now.date().isoformat()
        self.metric_repo.sync_registry()
        latest_quotes = self._latest_local_quotes(market)
        warnings: list[str] = []
        if not latest_quotes:
            warnings.append("missing_local_price_data")
            snapshot = self.market_repo.upsert_snapshot(
                market=market,
                snapshot_date=snapshot_date,
                as_of=as_of,
                status="insufficient_data",
                headline="本地数据库暂无可用行情，市场终端仅显示空状态。",
                summary={"universe_count": 0, "advance_count": 0, "decline_count": 0},
                coverage={"security_quotes": 0, "sectors": 0, "source": "prices"},
                data_quality={"warnings": warnings},
                source_count=0,
                observed_at=as_of,
                fetched_at=as_of,
                trading_date=snapshot_date,
                currency="CNY" if market == "CN" else None,
                unit="count",
                quality_status="insufficient_data",
                is_stale=False,
            )
            return MarketSnapshotResult(
                snapshot=snapshot,
                breadth=None,
                sectors=[],
                movers={"gainers": [], "losers": [], "turnover": []},
                warnings=warnings,
            )

        self.market_repo.upsert_security_quotes(latest_quotes)
        trade_date = str(latest_quotes[0]["trade_date"])
        breadth = self.market_repo.upsert_breadth(
            {
                "market": market,
                "trade_date": trade_date,
                "universe_count": len(latest_quotes),
                "advance_count": sum(1 for row in latest_quotes if _number(row.get("change_pct")) > 0),
                "decline_count": sum(1 for row in latest_quotes if _number(row.get("change_pct")) < 0),
                "flat_count": sum(1 for row in latest_quotes if _number(row.get("change_pct")) == 0),
                "limit_up_count": sum(1 for row in latest_quotes if _number(row.get("change_pct")) >= 0.095),
                "limit_down_count": sum(1 for row in latest_quotes if _number(row.get("change_pct")) <= -0.095),
                "above_ma20_count": 0,
                "above_ma60_count": 0,
                "total_amount": sum(_number(row.get("amount")) or 0.0 for row in latest_quotes),
                "data_source": "local_prices",
                "retrieved_at": as_of,
            }
        )
        sectors = self._sector_snapshots(market, trade_date, latest_quotes, as_of)
        self.market_repo.upsert_sector_snapshots(sectors)
        movers = _movers(latest_quotes)
        snapshot = self.market_repo.upsert_snapshot(
            market=market,
            snapshot_date=snapshot_date,
            as_of=as_of,
            status="draft",
            headline=f"{market} 本地行情覆盖 {len(latest_quotes)} 只证券，来源为本地价格表。",
            summary={
                "universe_count": len(latest_quotes),
                "advance_count": breadth["advance_count"],
                "decline_count": breadth["decline_count"],
                "flat_count": breadth["flat_count"],
                "total_amount": breadth["total_amount"],
                "latest_trade_date": trade_date,
            },
            coverage={
                "security_quotes": len(latest_quotes),
                "sectors": len(sectors),
                "source": "prices",
            },
            data_quality={"warnings": warnings, "publishable": False},
            source_count=len(latest_quotes),
            observed_at=trade_date,
            fetched_at=as_of,
            trading_date=trade_date,
            currency="CNY" if market == "CN" else None,
            unit="count",
            quality_status="draft",
            is_stale=False,
        )
        return MarketSnapshotResult(
            snapshot=snapshot,
            breadth=breadth,
            sectors=sectors,
            movers=movers,
            warnings=warnings,
        )

    def _latest_local_quotes(self, market: str) -> list[dict[str, object]]:
        with session_scope() as session:
            companies = {
                company.symbol: company
                for company in session.scalars(select(Company)).all()
                if _matches_market(company, market)
            }
            if not companies:
                return []
            prices = session.scalars(
                select(Price)
                .where(Price.symbol.in_(companies))
                .order_by(Price.symbol, Price.trade_date.desc())
            ).all()
            by_symbol: dict[str, list[Price]] = defaultdict(list)
            for price in prices:
                by_symbol[price.symbol].append(price)

            rows: list[dict[str, object]] = []
            for symbol, symbol_prices in by_symbol.items():
                latest = symbol_prices[0]
                previous = symbol_prices[1] if len(symbol_prices) > 1 else None
                close = latest.close
                prev_close = previous.close if previous else None
                change_pct = None
                if close is not None and prev_close not in (None, 0):
                    change_pct = close / prev_close - 1
                company = companies[symbol]
                rows.append(
                    {
                        "symbol": symbol,
                        "name": company.company_name,
                        "market": market,
                        "sector": company.industry or "未分类",
                        "industry": company.industry,
                        "trade_date": latest.trade_date,
                        "close": close,
                        "prev_close": prev_close,
                        "change_pct": change_pct,
                        "volume": latest.volume,
                        "amount": latest.amount,
                        "data_source": "local_prices",
                        "retrieved_at": latest.retrieved_at,
                    }
                )
        return sorted(rows, key=lambda row: str(row["trade_date"]), reverse=True)

    def _sector_snapshots(
        self,
        market: str,
        trade_date: str,
        quotes: list[dict[str, object]],
        as_of: str,
    ) -> list[dict[str, object]]:
        by_sector: dict[str, list[dict[str, object]]] = defaultdict(list)
        for quote in quotes:
            by_sector[str(quote.get("sector") or "未分类")].append(quote)

        rows: list[dict[str, object]] = []
        for sector_name, items in by_sector.items():
            changes = [
                value
                for value in (_number(item.get("change_pct")) for item in items)
                if value is not None
            ]
            rows.append(
                {
                    "market": market,
                    "sector_code": sector_name,
                    "sector_name": sector_name,
                    "trade_date": trade_date,
                    "constituents_count": len(items),
                    "advance_count": sum(1 for item in items if _number(item.get("change_pct")) > 0),
                    "decline_count": sum(1 for item in items if _number(item.get("change_pct")) < 0),
                    "flat_count": sum(1 for item in items if _number(item.get("change_pct")) == 0),
                    "avg_change_pct": fmean(changes) if changes else None,
                    "median_change_pct": median(changes) if changes else None,
                    "total_amount": sum(_number(item.get("amount")) or 0.0 for item in items),
                    "data_source": "local_prices",
                    "retrieved_at": as_of,
                }
            )
        return rows


def _matches_market(company: Company, market: str) -> bool:
    if market == "CN":
        return company.exchange in {"SSE", "SZSE", "BSE", None}
    return company.exchange == market


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _movers(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    with_change = [row for row in rows if _number(row.get("change_pct")) is not None]
    gainers = sorted(with_change, key=lambda row: _number(row.get("change_pct")) or 0.0, reverse=True)
    losers = sorted(with_change, key=lambda row: _number(row.get("change_pct")) or 0.0)
    turnover = sorted(rows, key=lambda row: _number(row.get("amount")) or 0.0, reverse=True)
    return {
        "gainers": gainers[:10],
        "losers": losers[:10],
        "turnover": turnover[:10],
    }
