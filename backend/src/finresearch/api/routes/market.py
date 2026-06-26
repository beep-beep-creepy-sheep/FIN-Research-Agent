from __future__ import annotations

from fastapi import APIRouter

from finresearch.repositories.market import MarketRepository


router = APIRouter()


@router.get("/overview")
def market_overview(market: str = "CN") -> dict[str, object]:
    repo = MarketRepository()
    snapshot = repo.latest_snapshot(market)
    breadth = repo.latest_breadth(market)
    sectors = repo.latest_sector_snapshots(market, limit=20)
    quotes = _latest_trade_date_rows(repo.list_security_quotes(market=market, limit=1000))
    indices = repo.latest_index_quotes(market=market, limit=20)
    if snapshot is None:
        snapshot = _empty_snapshot(market)
    return {
        "market": market,
        "snapshot": snapshot,
        "breadth": breadth,
        "sectors": sectors,
        "indices": indices,
        "movers": _movers(quotes),
        "charts": _overview_charts(snapshot, breadth, sectors, quotes, indices),
        "empty": not quotes and breadth is None and not sectors and not indices,
    }


@router.get("/indices")
def market_indices(market: str = "CN", limit: int = 20) -> dict[str, object]:
    rows = MarketRepository().latest_index_quotes(market=market, limit=limit)
    return {
        "market": market,
        "items": rows,
        "empty": not rows,
        "source": "index_quotes",
    }


@router.get("/breadth")
def market_breadth(market: str = "CN") -> dict[str, object]:
    row = MarketRepository().latest_breadth(market)
    return {
        "market": market,
        "item": row,
        "empty": row is None,
        "source": "market_breadth_snapshots",
    }


@router.get("/sectors")
def market_sectors(market: str = "CN", limit: int = 50) -> dict[str, object]:
    rows = MarketRepository().latest_sector_snapshots(market, limit=limit)
    return {
        "market": market,
        "items": rows,
        "empty": not rows,
        "source": "sector_snapshots",
    }


@router.get("/movers")
def market_movers(market: str = "CN", limit: int = 10) -> dict[str, object]:
    quotes = _latest_trade_date_rows(MarketRepository().list_security_quotes(market=market, limit=1000))
    movers = _movers(quotes, limit=limit)
    return {
        "market": market,
        "items": movers,
        "empty": not any(movers.values()),
        "source": "security_quotes",
    }


def _empty_snapshot(market: str) -> dict[str, object]:
    return {
        "market": market,
        "status": "no_snapshot",
        "headline": "尚未生成市场快照。",
        "summary": {"universe_count": 0, "advance_count": 0, "decline_count": 0},
        "coverage": {"security_quotes": 0, "sectors": 0},
        "data_quality": {"warnings": ["missing_market_snapshot"]},
        "source_count": 0,
    }


def _latest_trade_date_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    trade_dates = [str(row["trade_date"]) for row in rows if row.get("trade_date")]
    if not trade_dates:
        return []
    latest = max(trade_dates)
    return [row for row in rows if row.get("trade_date") == latest]


def _movers(rows: list[dict[str, object]], limit: int = 10) -> dict[str, list[dict[str, object]]]:
    with_change = [row for row in rows if _number(row.get("change_pct")) is not None]
    return {
        "gainers": sorted(
            with_change,
            key=lambda row: _number(row.get("change_pct")) or 0.0,
            reverse=True,
        )[:limit],
        "losers": sorted(with_change, key=lambda row: _number(row.get("change_pct")) or 0.0)[:limit],
        "turnover": sorted(rows, key=lambda row: _number(row.get("amount")) or 0.0, reverse=True)[
            :limit
        ],
    }


def _overview_charts(
    snapshot: dict[str, object],
    breadth: dict[str, object] | None,
    sectors: list[dict[str, object]],
    quotes: list[dict[str, object]],
    indices: list[dict[str, object]],
) -> list[dict[str, object]]:
    source_note = "来源：本地 PostgreSQL/SQLite 行情快照；无数据时不造点。"
    coverage = _dict_value(snapshot.get("coverage"))
    return [
        _chart({
            "id": "breadth_pie",
            "title": "涨跌家数",
            "kind": "pie",
            "unit": "家",
            "as_of": snapshot.get("as_of"),
            "source": "market_breadth_snapshots",
            "empty": breadth is None,
            "note": source_note,
            "data": [] if breadth is None else [
                {"name": "上涨", "value": breadth["advance_count"]},
                {"name": "下跌", "value": breadth["decline_count"]},
                {"name": "平盘", "value": breadth["flat_count"]},
            ],
        }, frequency="daily"),
        _chart({
            "id": "sector_change",
            "title": "板块平均涨跌幅",
            "kind": "bar",
            "unit": "%",
            "as_of": snapshot.get("as_of"),
            "source": "sector_snapshots",
            "empty": not sectors,
            "note": source_note,
            "data": [
                {"name": row["sector_name"], "value": _percent(row.get("avg_change_pct"))}
                for row in sectors[:20]
            ],
        }, frequency="daily"),
        _chart({
            "id": "turnover_top",
            "title": "成交额前列",
            "kind": "bar",
            "unit": "元",
            "as_of": snapshot.get("as_of"),
            "source": "security_quotes",
            "empty": not quotes,
            "note": source_note,
            "data": [{"name": row["symbol"], "value": row.get("amount")} for row in quotes[:20]],
        }, frequency="daily", currency="CNY"),
        _chart({
            "id": "mover_distribution",
            "title": "涨跌幅分布",
            "kind": "histogram",
            "unit": "%",
            "as_of": snapshot.get("as_of"),
            "source": "security_quotes",
            "empty": not quotes,
            "note": source_note,
            "data": _distribution(quotes),
        }, frequency="daily"),
        _chart({
            "id": "index_latest",
            "title": "指数最新收盘",
            "kind": "bar",
            "unit": "点",
            "as_of": snapshot.get("as_of"),
            "source": "index_quotes",
            "empty": not indices,
            "note": source_note,
            "data": [{"name": row["index_name"] or row["index_code"], "value": row.get("close")} for row in indices],
        }, frequency="daily"),
        _chart({
            "id": "coverage",
            "title": "本地覆盖度",
            "kind": "bar",
            "unit": "条",
            "as_of": snapshot.get("as_of"),
            "source": "market_snapshots",
            "empty": False,
            "note": source_note,
            "data": [
                {"name": "证券", "value": coverage.get("security_quotes", 0)},
                {"name": "板块", "value": coverage.get("sectors", 0)},
                {"name": "来源", "value": snapshot.get("source_count", 0)},
            ],
        }, frequency="daily"),
    ]


def _chart(chart: dict[str, object], *, frequency: str, currency: str | None = None) -> dict[str, object]:
    chart["frequency"] = frequency
    chart["currency"] = currency
    chart["updated_at"] = chart.get("as_of")
    chart["quality_status"] = "empty" if chart.get("empty") else "ok"
    chart["warnings"] = ["missing_source_data"] if chart.get("empty") else []
    chart["error"] = None
    return chart


def _distribution(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets = {
        "<-5%": 0,
        "-5%~-2%": 0,
        "-2%~0": 0,
        "0~2%": 0,
        "2%~5%": 0,
        ">5%": 0,
    }
    for row in rows:
        value = _number(row.get("change_pct"))
        if value is None:
            continue
        pct = value * 100
        if pct < -5:
            buckets["<-5%"] += 1
        elif pct < -2:
            buckets["-5%~-2%"] += 1
        elif pct < 0:
            buckets["-2%~0"] += 1
        elif pct < 2:
            buckets["0~2%"] += 1
        elif pct < 5:
            buckets["2%~5%"] += 1
        else:
            buckets[">5%"] += 1
    return [{"name": key, "value": value} for key, value in buckets.items()]


def _number(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, str | bytes | int | float):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percent(value: object) -> float | None:
    number = _number(value)
    return None if number is None else number * 100


def _dict_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
