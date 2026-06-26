from __future__ import annotations

from sqlalchemy import select

from finresearch.database.models import (
    IndexQuote,
    MarketBreadthSnapshot,
    MarketSnapshot,
    MetricDefinitionModel,
    SectorSnapshot,
    SecurityQuote,
)
from finresearch.database.session import session_scope
from finresearch.metrics import MetricDefinition, list_metric_definitions


class MetricDefinitionRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def sync_registry(self, definitions: list[MetricDefinition] | None = None) -> int:
        definitions = definitions or list_metric_definitions()
        with session_scope() as session:
            for definition in definitions:
                row = session.get(MetricDefinitionModel, definition.code)
                if row is None:
                    row = MetricDefinitionModel(code=definition.code)
                    session.add(row)
                row.name_en = definition.name_en
                row.name_zh = definition.name_zh
                row.category = definition.category
                row.formula = definition.formula
                row.inputs = list(definition.inputs)
                row.unit = definition.unit
                row.periodicity = definition.periodicity
                row.source_requirement = definition.source_requirement
                row.applicable_industries = list(definition.applicable_industries)
                row.caveats = definition.caveats
                row.calculation_version = definition.calculation_version
                row.missing_behavior = definition.missing_behavior
        return len(definitions)

    def list(self) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(select(MetricDefinitionModel).order_by(MetricDefinitionModel.code)).all()
            return [
                {
                    "code": row.code,
                    "name_en": row.name_en,
                    "name_zh": row.name_zh,
                    "category": row.category,
                    "formula": row.formula,
                    "inputs": row.inputs,
                    "unit": row.unit,
                    "periodicity": row.periodicity,
                    "source_requirement": row.source_requirement,
                    "applicable_industries": row.applicable_industries,
                    "caveats": row.caveats,
                    "calculation_version": row.calculation_version,
                    "missing_behavior": row.missing_behavior,
                }
                for row in rows
            ]


class MarketRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def upsert_snapshot(
        self,
        *,
        market: str,
        snapshot_date: str,
        as_of: str,
        status: str,
        headline: str | None,
        summary: dict[str, object],
        coverage: dict[str, object],
        data_quality: dict[str, object],
        source_count: int,
        data_source: str = "local_database",
        observed_at: str | None = None,
        fetched_at: str | None = None,
        trading_date: str | None = None,
        currency: str | None = None,
        unit: str | None = None,
        quality_status: str | None = None,
        is_stale: bool = False,
    ) -> dict[str, object]:
        with session_scope() as session:
            row = session.scalar(
                select(MarketSnapshot).where(
                    MarketSnapshot.market == market,
                    MarketSnapshot.snapshot_date == snapshot_date,
                    MarketSnapshot.data_source == data_source,
                )
            )
            if row is None:
                row = MarketSnapshot(
                    market=market,
                    snapshot_date=snapshot_date,
                    data_source=data_source,
                )
                session.add(row)
            row.as_of = as_of
            row.observed_at = observed_at or as_of
            row.fetched_at = fetched_at or as_of
            row.trading_date = trading_date or snapshot_date
            row.currency = currency
            row.unit = unit
            row.quality_status = quality_status or status
            row.is_stale = is_stale
            row.status = status
            row.headline = headline
            row.summary = summary
            row.coverage = coverage
            row.data_quality = data_quality
            row.source_count = source_count
            session.flush()
            return _snapshot_dict(row)

    def latest_snapshot(self, market: str = "CN") -> dict[str, object] | None:
        with session_scope() as session:
            row = session.scalar(
                select(MarketSnapshot)
                .where(MarketSnapshot.market == market)
                .order_by(MarketSnapshot.snapshot_date.desc(), MarketSnapshot.id.desc())
                .limit(1)
            )
            return _snapshot_dict(row) if row else None

    def upsert_security_quotes(self, rows: list[dict[str, object]]) -> int:
        if not rows:
            return 0
        with session_scope() as session:
            for payload in rows:
                row = session.scalar(
                    select(SecurityQuote).where(
                        SecurityQuote.symbol == str(payload["symbol"]),
                        SecurityQuote.trade_date == str(payload["trade_date"]),
                        SecurityQuote.data_source == str(payload["data_source"]),
                    )
                )
                if row is None:
                    row = SecurityQuote(
                        symbol=str(payload["symbol"]),
                        trade_date=str(payload["trade_date"]),
                        data_source=str(payload["data_source"]),
                    )
                    session.add(row)
                _assign(row, payload, SECURITY_QUOTE_FIELDS)
        return len(rows)

    def list_security_quotes(
        self,
        *,
        market: str | None = None,
        trade_date: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, object]]:
        with session_scope() as session:
            statement = select(SecurityQuote)
            if market:
                statement = statement.where(SecurityQuote.market == market)
            if trade_date:
                statement = statement.where(SecurityQuote.trade_date == trade_date)
            rows = session.scalars(
                statement.order_by(SecurityQuote.trade_date.desc(), SecurityQuote.symbol).limit(limit)
            ).all()
            return [_security_quote_dict(row) for row in rows]

    def upsert_index_quotes(self, rows: list[dict[str, object]]) -> int:
        if not rows:
            return 0
        with session_scope() as session:
            for payload in rows:
                row = session.scalar(
                    select(IndexQuote).where(
                        IndexQuote.index_code == str(payload["index_code"]),
                        IndexQuote.trade_date == str(payload["trade_date"]),
                        IndexQuote.data_source == str(payload["data_source"]),
                    )
                )
                if row is None:
                    row = IndexQuote(
                        index_code=str(payload["index_code"]),
                        trade_date=str(payload["trade_date"]),
                        data_source=str(payload["data_source"]),
                    )
                    session.add(row)
                _assign(row, payload, INDEX_QUOTE_FIELDS)
        return len(rows)

    def latest_index_quotes(self, *, market: str | None = None, limit: int = 20) -> list[dict[str, object]]:
        with session_scope() as session:
            statement = select(IndexQuote)
            if market:
                statement = statement.where(IndexQuote.market == market)
            rows = session.scalars(
                statement.order_by(IndexQuote.trade_date.desc(), IndexQuote.index_code).limit(limit)
            ).all()
            return [_index_quote_dict(row) for row in rows]

    def upsert_breadth(self, payload: dict[str, object]) -> dict[str, object]:
        with session_scope() as session:
            row = session.scalar(
                select(MarketBreadthSnapshot).where(
                    MarketBreadthSnapshot.market == str(payload["market"]),
                    MarketBreadthSnapshot.trade_date == str(payload["trade_date"]),
                    MarketBreadthSnapshot.data_source == str(payload["data_source"]),
                )
            )
            if row is None:
                row = MarketBreadthSnapshot(
                    market=str(payload["market"]),
                    trade_date=str(payload["trade_date"]),
                    data_source=str(payload["data_source"]),
                )
                session.add(row)
            _assign(row, payload, BREADTH_FIELDS)
            session.flush()
            return _breadth_dict(row)

    def latest_breadth(self, market: str = "CN") -> dict[str, object] | None:
        with session_scope() as session:
            row = session.scalar(
                select(MarketBreadthSnapshot)
                .where(MarketBreadthSnapshot.market == market)
                .order_by(MarketBreadthSnapshot.trade_date.desc(), MarketBreadthSnapshot.id.desc())
                .limit(1)
            )
            return _breadth_dict(row) if row else None

    def upsert_sector_snapshots(self, rows: list[dict[str, object]]) -> int:
        if not rows:
            return 0
        with session_scope() as session:
            for payload in rows:
                row = session.scalar(
                    select(SectorSnapshot).where(
                        SectorSnapshot.market == str(payload["market"]),
                        SectorSnapshot.sector_code == str(payload["sector_code"]),
                        SectorSnapshot.trade_date == str(payload["trade_date"]),
                        SectorSnapshot.data_source == str(payload["data_source"]),
                    )
                )
                if row is None:
                    row = SectorSnapshot(
                        market=str(payload["market"]),
                        sector_code=str(payload["sector_code"]),
                        trade_date=str(payload["trade_date"]),
                        data_source=str(payload["data_source"]),
                    )
                    session.add(row)
                _assign(row, payload, SECTOR_SNAPSHOT_FIELDS)
        return len(rows)

    def latest_sector_snapshots(self, market: str = "CN", limit: int = 50) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(SectorSnapshot)
                .where(SectorSnapshot.market == market)
                .order_by(SectorSnapshot.trade_date.desc(), SectorSnapshot.avg_change_pct.desc())
                .limit(limit)
            ).all()
            return [_sector_snapshot_dict(row) for row in rows]


SECURITY_QUOTE_FIELDS = (
    "company_id",
    "name",
    "market",
    "sector",
    "industry",
    "close",
    "prev_close",
    "change_pct",
    "volume",
    "amount",
    "market_cap",
    "pe",
    "pb",
    "ps",
    "turnover_rate",
    "retrieved_at",
)
INDEX_QUOTE_FIELDS = (
    "index_name",
    "market",
    "open",
    "high",
    "low",
    "close",
    "prev_close",
    "change_pct",
    "volume",
    "amount",
    "retrieved_at",
)
BREADTH_FIELDS = (
    "universe_count",
    "advance_count",
    "decline_count",
    "flat_count",
    "limit_up_count",
    "limit_down_count",
    "above_ma20_count",
    "above_ma60_count",
    "total_amount",
    "retrieved_at",
)
SECTOR_SNAPSHOT_FIELDS = (
    "sector_name",
    "constituents_count",
    "advance_count",
    "decline_count",
    "flat_count",
    "avg_change_pct",
    "median_change_pct",
    "total_amount",
    "retrieved_at",
)


def _assign(row: object, payload: dict[str, object], fields: tuple[str, ...]) -> None:
    for field in fields:
        if field in payload:
            setattr(row, field, payload[field])


def _snapshot_dict(row: MarketSnapshot) -> dict[str, object]:
    return {
        "id": row.id,
        "market": row.market,
        "snapshot_date": row.snapshot_date,
        "as_of": row.as_of,
        "observed_at": row.observed_at,
        "fetched_at": row.fetched_at,
        "trading_date": row.trading_date,
        "currency": row.currency,
        "unit": row.unit,
        "quality_status": row.quality_status,
        "is_stale": row.is_stale,
        "status": row.status,
        "headline": row.headline,
        "summary": row.summary,
        "coverage": row.coverage,
        "data_quality": row.data_quality,
        "source_count": row.source_count,
        "data_source": row.data_source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _security_quote_dict(row: SecurityQuote) -> dict[str, object]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "name": row.name,
        "market": row.market,
        "sector": row.sector,
        "industry": row.industry,
        "trade_date": row.trade_date,
        "close": row.close,
        "prev_close": row.prev_close,
        "change_pct": row.change_pct,
        "volume": row.volume,
        "amount": row.amount,
        "market_cap": row.market_cap,
        "pe": row.pe,
        "pb": row.pb,
        "ps": row.ps,
        "turnover_rate": row.turnover_rate,
        "data_source": row.data_source,
        "retrieved_at": row.retrieved_at,
    }


def _index_quote_dict(row: IndexQuote) -> dict[str, object]:
    return {
        "id": row.id,
        "index_code": row.index_code,
        "index_name": row.index_name,
        "market": row.market,
        "trade_date": row.trade_date,
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "prev_close": row.prev_close,
        "change_pct": row.change_pct,
        "volume": row.volume,
        "amount": row.amount,
        "data_source": row.data_source,
        "retrieved_at": row.retrieved_at,
    }


def _breadth_dict(row: MarketBreadthSnapshot) -> dict[str, object]:
    return {
        "id": row.id,
        "market": row.market,
        "trade_date": row.trade_date,
        "universe_count": row.universe_count,
        "advance_count": row.advance_count,
        "decline_count": row.decline_count,
        "flat_count": row.flat_count,
        "limit_up_count": row.limit_up_count,
        "limit_down_count": row.limit_down_count,
        "above_ma20_count": row.above_ma20_count,
        "above_ma60_count": row.above_ma60_count,
        "total_amount": row.total_amount,
        "data_source": row.data_source,
        "retrieved_at": row.retrieved_at,
    }


def _sector_snapshot_dict(row: SectorSnapshot) -> dict[str, object]:
    return {
        "id": row.id,
        "market": row.market,
        "sector_code": row.sector_code,
        "sector_name": row.sector_name,
        "trade_date": row.trade_date,
        "constituents_count": row.constituents_count,
        "advance_count": row.advance_count,
        "decline_count": row.decline_count,
        "flat_count": row.flat_count,
        "avg_change_pct": row.avg_change_pct,
        "median_change_pct": row.median_change_pct,
        "total_amount": row.total_amount,
        "data_source": row.data_source,
        "retrieved_at": row.retrieved_at,
    }
