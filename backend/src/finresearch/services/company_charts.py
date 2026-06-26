from __future__ import annotations

from pathlib import Path

from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository


class CompanyChartService:
    def __init__(self, library_path: Path) -> None:
        self.fact_repo = FinancialFactRepository(library_path)
        self.price_repo = PriceRepository(library_path)

    def build(self, symbol: str, *, years: int = 10) -> list[dict[str, object]]:
        matrix = list(reversed(self.fact_repo.matrix(symbol, years=years)))
        prices = list(reversed(self.price_repo.list_by_symbol(symbol, limit=260)))
        return [
            _kline_chart(prices),
            _financial_trend_chart(matrix),
            _margin_chart(matrix),
            _returns_chart(matrix),
            _valuation_band_chart(matrix, prices),
        ]


def _kline_chart(prices: list[dict[str, object]]) -> dict[str, object]:
    return _with_metadata({
        "id": "kline_volume",
        "title": "K线与成交量",
        "kind": "candlestick",
        "unit": "价格/成交量",
        "as_of": prices[-1]["trade_date"] if prices else None,
        "source": _source(prices, "prices"),
        "empty": not prices,
        "note": "价格来自本地 prices 表；抓取失败时不生成替代行情。",
        "data": [
            {
                "name": row["trade_date"],
                "open": row.get("open"),
                "close": row.get("close"),
                "low": row.get("low"),
                "high": row.get("high"),
                "volume": row.get("volume"),
            }
            for row in prices
        ],
    }, frequency="daily", currency="CNY")


def _financial_trend_chart(matrix: list[dict[str, object]]) -> dict[str, object]:
    return _with_metadata({
        "id": "financial_trend",
        "title": "收入 / 净利润 / 经营现金流",
        "kind": "line",
        "unit": "元",
        "as_of": _latest_period(matrix),
        "source": "financial_facts",
        "empty": not matrix,
        "note": "所有数值来自本地结构化财务事实表。",
        "series": [
            {"name": "营业收入", "field": "revenue"},
            {"name": "净利润", "field": "net_profit_parent"},
            {"name": "经营现金流", "field": "operating_cash_flow"},
        ],
        "data": [
            {
                "name": row["period_end"],
                "revenue": row.get("revenue"),
                "net_profit_parent": row.get("net_profit_parent") or row.get("net_profit"),
                "operating_cash_flow": row.get("operating_cash_flow"),
            }
            for row in matrix
        ],
    }, frequency="annual", currency="CNY")


def _margin_chart(matrix: list[dict[str, object]]) -> dict[str, object]:
    rows = []
    for row in matrix:
        revenue = _number(row.get("revenue"))
        rows.append(
            {
                "name": row["period_end"],
                "gross_margin": _ratio(row.get("gross_profit"), revenue),
                "operating_margin": _ratio(row.get("operating_profit"), revenue),
                "net_margin": _ratio(row.get("net_profit_parent") or row.get("net_profit"), revenue),
            }
        )
    return _with_metadata({
        "id": "margin_trend",
        "title": "利润率趋势",
        "kind": "line",
        "unit": "%",
        "as_of": _latest_period(matrix),
        "source": "financial_facts",
        "empty": not any(_has_value(row, "gross_margin", "operating_margin", "net_margin") for row in rows),
        "note": "毛利率需要 gross_profit，营业利润率需要 operating_profit；缺字段则留空。",
        "series": [
            {"name": "毛利率", "field": "gross_margin"},
            {"name": "营业利润率", "field": "operating_margin"},
            {"name": "净利率", "field": "net_margin"},
        ],
        "data": rows,
    }, frequency="annual")


def _returns_chart(matrix: list[dict[str, object]]) -> dict[str, object]:
    rows = []
    for row in matrix:
        net_profit = row.get("net_profit_parent") or row.get("net_profit")
        rows.append(
            {
                "name": row["period_end"],
                "roe": _ratio(net_profit, row.get("total_equity") or row.get("equity_parent")),
                "roa": _ratio(net_profit, row.get("total_assets")),
            }
        )
    return _with_metadata({
        "id": "returns_trend",
        "title": "ROE / ROA",
        "kind": "line",
        "unit": "%",
        "as_of": _latest_period(matrix),
        "source": "financial_facts",
        "empty": not any(_has_value(row, "roe", "roa") for row in rows),
        "note": "ROE/ROA 使用最新期资产和权益近似计算，正式报告会展示公式口径。",
        "series": [{"name": "ROE", "field": "roe"}, {"name": "ROA", "field": "roa"}],
        "data": rows,
    }, frequency="annual")


def _valuation_band_chart(
    matrix: list[dict[str, object]],
    prices: list[dict[str, object]],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    latest_profit = _number(matrix[-1].get("net_profit_parent") or matrix[-1].get("net_profit")) if matrix else None
    shares = _number(matrix[-1].get("shares_outstanding")) if matrix else None
    if latest_profit and shares:
        eps = latest_profit / shares
        for row in prices:
            close = _number(row.get("close"))
            rows.append({"name": row["trade_date"], "pe": None if close is None or eps == 0 else close / eps})
    return _with_metadata({
        "id": "valuation_band",
        "title": "估值区间",
        "kind": "line",
        "unit": "倍",
        "as_of": prices[-1]["trade_date"] if prices else _latest_period(matrix),
        "source": "prices + financial_facts",
        "empty": not rows,
        "note": "估值区间需要价格、股本和利润数据；缺任一项则拒绝生成。",
        "series": [{"name": "PE", "field": "pe"}],
        "data": rows,
    }, frequency="daily")


def _with_metadata(chart: dict[str, object], *, frequency: str, currency: str | None = None) -> dict[str, object]:
    chart["frequency"] = frequency
    chart["currency"] = currency
    chart["updated_at"] = chart.get("as_of")
    chart["quality_status"] = "empty" if chart.get("empty") else "ok"
    chart["warnings"] = ["missing_source_data"] if chart.get("empty") else []
    chart["error"] = None
    return chart


def _latest_period(matrix: list[dict[str, object]]) -> str | None:
    return str(matrix[-1]["period_end"]) if matrix else None


def _source(rows: list[dict[str, object]], fallback: str) -> str:
    sources = {str(row.get("data_source")) for row in rows if row.get("data_source")}
    return ", ".join(sorted(sources)) if sources else fallback


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(numerator: object, denominator: object) -> float | None:
    left = _number(numerator)
    right = _number(denominator)
    if left is None or right in (None, 0):
        return None
    return left / right


def _has_value(row: dict[str, object], *keys: str) -> bool:
    return any(row.get(key) is not None for key in keys)
