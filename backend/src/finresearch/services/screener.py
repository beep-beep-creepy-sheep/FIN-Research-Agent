from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass
from typing import cast

from sqlalchemy import case, func, or_, select

from finresearch.database.models import Company, FinancialFact, ScreenPreset
from finresearch.database.session import session_scope


@dataclass(frozen=True)
class ScreenQuery:
    q: str | None = None
    market: str | None = None
    exchange: str | None = None
    industry: str | None = None
    sector: str | None = None
    listing_board: str | None = None
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    min_liquidity: float | None = None
    min_revenue: float | None = None
    min_revenue_growth: float | None = None
    min_net_profit_growth: float | None = None
    min_net_margin: float | None = None
    min_roe: float | None = None
    min_roic: float | None = None
    min_gross_margin: float | None = None
    min_fcf_yield: float | None = None
    max_debt_to_assets: float | None = None
    max_net_debt_to_ebitda: float | None = None
    min_cash_conversion: float | None = None
    min_current_ratio: float | None = None
    max_pe_ttm: float | None = None
    max_ev_ebitda: float | None = None
    min_relative_percentile: float | None = None
    valuation_scenario_status: str | None = None
    max_volatility: float | None = None
    max_drawdown: float | None = None
    max_beta: float | None = None
    min_data_quality_score: float | None = None
    official_source_coverage: str | None = None
    missing_filing: bool | None = None
    source_conflict: bool | None = None
    insufficient_data: bool | None = None
    min_overall_research_quality_score: float | None = None
    min_growth_score: float | None = None
    min_profitability_score: float | None = None
    min_cash_flow_quality_score: float | None = None
    min_balance_sheet_score: float | None = None
    min_earnings_quality_score: float | None = None
    industry_pack: str | None = None
    max_risk_flag_count: int | None = None
    max_liability_ratio: float | None = None
    include_missing: bool = False
    sort_by: str = "revenue"
    sort_direction: str = "desc"
    offset: int = 0
    limit: int = 50


class ScreenerService:
    def query(self, request: ScreenQuery) -> dict[str, object]:
        if request.sort_by not in SORT_EXPRESSIONS:
            raise ValueError(f"invalid_sort_by:{request.sort_by}")
        if request.sort_direction not in {"asc", "desc"}:
            raise ValueError(f"invalid_sort_direction:{request.sort_direction}")
        latest_period = (
            select(
                FinancialFact.symbol.label("symbol"),
                func.max(FinancialFact.period_end).label("period_end"),
            )
            .group_by(FinancialFact.symbol)
            .subquery()
        )
        revenue = _metric_expr("revenue")
        net_profit = _metric_expr("net_profit", "net_profit_parent")
        revenue_growth = _metric_expr("revenue_yoy", "revenue_growth")
        net_profit_growth = _metric_expr("net_profit_yoy", "net_profit_growth")
        assets = _metric_expr("total_assets")
        liabilities = _metric_expr("total_liabilities")
        equity = _metric_expr("total_equity", "equity_parent")
        market_cap = _metric_expr("market_cap")
        fcf = _metric_expr("fcf", "fcf_ttm")
        ebitda = _metric_expr("ebitda", "ebitda_ttm")
        net_debt = _metric_expr("net_debt")
        current_assets = _metric_expr("current_assets")
        current_liabilities = _metric_expr("current_liabilities")
        operating_cash_flow = _metric_expr("operating_cash_flow")
        gross_profit = _metric_expr("gross_profit")
        operating_profit = _metric_expr("operating_profit")
        net_margin = net_profit / func.nullif(revenue, 0)
        roe = net_profit / func.nullif(equity, 0)
        roic = operating_profit / func.nullif(assets - current_liabilities, 0)
        gross_margin = gross_profit / func.nullif(revenue, 0)
        liability_ratio = liabilities / func.nullif(assets, 0)
        fcf_yield = fcf / func.nullif(market_cap, 0)
        net_debt_to_ebitda = net_debt / func.nullif(ebitda, 0)
        cash_conversion = operating_cash_flow / func.nullif(net_profit, 0)
        current_ratio = current_assets / func.nullif(current_liabilities, 0)
        pe_ttm = market_cap / func.nullif(net_profit, 0)
        ev_ebitda = (market_cap + net_debt) / func.nullif(ebitda, 0)

        statement = (
            select(
                Company.symbol,
                Company.company_name,
                Company.exchange,
                Company.industry,
                latest_period.c.period_end,
                revenue.label("revenue"),
                net_profit.label("net_profit"),
                market_cap.label("market_cap"),
                revenue_growth.label("revenue_growth"),
                net_profit_growth.label("net_profit_growth"),
                gross_margin.label("gross_margin"),
                net_margin.label("net_margin"),
                roe.label("roe"),
                roic.label("roic"),
                liability_ratio.label("liability_ratio"),
                fcf_yield.label("fcf_yield"),
                net_debt_to_ebitda.label("net_debt_to_ebitda"),
                cash_conversion.label("cash_conversion"),
                current_ratio.label("current_ratio"),
                pe_ttm.label("pe_ttm"),
                ev_ebitda.label("ev_ebitda"),
                func.count(FinancialFact.id).label("local_fact_count"),
            )
            .join(FinancialFact, FinancialFact.symbol == Company.symbol)
            .join(
                latest_period,
                (latest_period.c.symbol == FinancialFact.symbol)
                & (latest_period.c.period_end == FinancialFact.period_end),
            )
            .group_by(
                Company.symbol,
                Company.company_name,
                Company.exchange,
                Company.industry,
                latest_period.c.period_end,
            )
        )
        if request.q:
            pattern = f"%{request.q}%"
            statement = statement.where(
                or_(Company.symbol.ilike(pattern), Company.company_name.ilike(pattern))
            )
        if request.industry:
            statement = statement.where(Company.industry == request.industry)
        if request.exchange:
            statement = statement.where(Company.exchange == request.exchange)
        if request.market:
            statement = statement.where(Company.exchange.in_(_market_exchanges(request.market)))
        if request.sector:
            statement = statement.where(Company.industry.ilike(f"%{request.sector}%"))
        if request.listing_board:
            prefixes = _board_prefixes(request.listing_board)
            if prefixes:
                statement = statement.where(or_(*[Company.symbol.like(f"{prefix}%") for prefix in prefixes]))
        if request.min_revenue is not None:
            statement = _having_min(statement, revenue, request.min_revenue, request.include_missing)
        if request.min_market_cap is not None:
            statement = _having_min(statement, market_cap, request.min_market_cap, request.include_missing)
        if request.max_market_cap is not None:
            statement = _having_max(statement, market_cap, request.max_market_cap, request.include_missing)
        if request.min_revenue_growth is not None:
            statement = _having_min(statement, revenue_growth, request.min_revenue_growth, request.include_missing)
        if request.min_net_profit_growth is not None:
            statement = _having_min(statement, net_profit_growth, request.min_net_profit_growth, request.include_missing)
        if request.min_net_margin is not None:
            statement = _having_min(statement, net_margin, request.min_net_margin, request.include_missing)
        if request.min_roe is not None:
            statement = _having_min(statement, roe, request.min_roe, request.include_missing)
        if request.min_roic is not None:
            statement = _having_min(statement, roic, request.min_roic, request.include_missing)
        if request.min_gross_margin is not None:
            statement = _having_min(statement, gross_margin, request.min_gross_margin, request.include_missing)
        if request.min_fcf_yield is not None:
            statement = _having_min(statement, fcf_yield, request.min_fcf_yield, request.include_missing)
        if request.max_liability_ratio is not None:
            statement = _having_max(statement, liability_ratio, request.max_liability_ratio, request.include_missing)
        if request.max_debt_to_assets is not None:
            statement = _having_max(statement, liability_ratio, request.max_debt_to_assets, request.include_missing)
        if request.max_net_debt_to_ebitda is not None:
            statement = _having_max(statement, net_debt_to_ebitda, request.max_net_debt_to_ebitda, request.include_missing)
        if request.min_cash_conversion is not None:
            statement = _having_min(statement, cash_conversion, request.min_cash_conversion, request.include_missing)
        if request.min_current_ratio is not None:
            statement = _having_min(statement, current_ratio, request.min_current_ratio, request.include_missing)
        if request.max_pe_ttm is not None:
            statement = _having_max(statement, pe_ttm, request.max_pe_ttm, request.include_missing)
        if request.max_ev_ebitda is not None:
            statement = _having_max(statement, ev_ebitda, request.max_ev_ebitda, request.include_missing)
        sort_expr = _sort_expr(request.sort_by)
        statement = statement.order_by(
            sort_expr.asc() if request.sort_direction == "asc" else sort_expr.desc()
        ).offset(max(0, request.offset)).limit(max(1, min(request.limit, 200)))

        with session_scope() as session:
            rows = [dict(row._mapping) for row in session.execute(statement).all()]
        for row in rows:
            row["data_quality_status"] = "partial" if _has_missing(row) else "available"
            row["missing_metrics"] = [key for key in DISPLAY_METRICS if row.get(key) is None]
            row["valuation_status"] = _valuation_status(row)
        as_of_values = [str(row["period_end"]) for row in rows if row.get("period_end") is not None]
        return {
            "rows": rows,
            "count": len(rows),
            "offset": max(0, request.offset),
            "limit": max(1, min(request.limit, 200)),
            "as_of": max(as_of_values) if as_of_values else None,
            "updated_at": max(as_of_values) if as_of_values else None,
            "filters": request.__dict__,
            "available_filters": sorted(asdict(ScreenQuery()).keys()),
            "data_quality": {
                "source": "financial_facts",
                "note": "筛选仅使用本地数据库最新财务期间；缺字段公司不会被强行补值。",
            },
        }

    def save_preset(self, name: str, filters: dict[str, object]) -> dict[str, object]:
        if not name.strip():
            raise ValueError("preset_name_required")
        with session_scope() as session:
            preset = session.scalar(select(ScreenPreset).where(ScreenPreset.name == name.strip()))
            if preset is None:
                preset = ScreenPreset(name=name.strip(), filters_json=filters)
                session.add(preset)
            else:
                preset.filters_json = filters
            session.flush()
            return _preset_dict(preset)

    def list_presets(self) -> list[dict[str, object]]:
        with session_scope() as session:
            return [_preset_dict(row) for row in session.scalars(select(ScreenPreset).order_by(ScreenPreset.name)).all()]

    def export(self, request: ScreenQuery, *, fmt: str) -> tuple[str, str]:
        payload = self.query(request)
        if fmt == "json":
            import json

            return "application/json", json.dumps(payload, ensure_ascii=False)
        if fmt != "csv":
            raise ValueError("invalid_export_format")
        output = io.StringIO()
        fields = ["symbol", "company_name", "exchange", "industry", "period_end", *DISPLAY_METRICS, "data_quality_status", "valuation_status"]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        rows = payload.get("rows", [])
        if isinstance(rows, list):
            for row in cast(list[dict[str, object]], rows):
                writer.writerow(row)
        return "text/csv", output.getvalue()


def _metric_expr(*codes: str):
    return func.max(case((FinancialFact.metric_code.in_(codes), FinancialFact.value)))


def _sort_expr(sort_by: str):
    return SORT_EXPRESSIONS[sort_by]()


SORT_EXPRESSIONS = {
    "revenue": lambda: _metric_expr("revenue"),
    "net_profit": lambda: _metric_expr("net_profit", "net_profit_parent"),
    "net_margin": lambda: _metric_expr("net_profit", "net_profit_parent")
    / func.nullif(_metric_expr("revenue"), 0),
    "roe": lambda: _metric_expr("net_profit", "net_profit_parent")
    / func.nullif(_metric_expr("total_equity", "equity_parent"), 0),
    "liability_ratio": lambda: _metric_expr("total_liabilities") / func.nullif(_metric_expr("total_assets"), 0),
    "market_cap": lambda: _metric_expr("market_cap"),
    "fcf_yield": lambda: _metric_expr("fcf", "fcf_ttm") / func.nullif(_metric_expr("market_cap"), 0),
    "pe_ttm": lambda: _metric_expr("market_cap") / func.nullif(_metric_expr("net_profit", "net_profit_parent"), 0),
    "ev_ebitda": lambda: (_metric_expr("market_cap") + _metric_expr("net_debt")) / func.nullif(_metric_expr("ebitda", "ebitda_ttm"), 0),
}

DISPLAY_METRICS = (
    "revenue",
    "net_profit",
    "market_cap",
    "revenue_growth",
    "net_profit_growth",
    "gross_margin",
    "net_margin",
    "roe",
    "roic",
    "liability_ratio",
    "fcf_yield",
    "net_debt_to_ebitda",
    "cash_conversion",
    "current_ratio",
    "pe_ttm",
    "ev_ebitda",
)


def _having_min(statement, expression, value: float, include_missing: bool):
    condition = expression >= value
    if include_missing:
        condition = condition | (expression.is_(None))
    return statement.having(condition)


def _having_max(statement, expression, value: float, include_missing: bool):
    condition = expression <= value
    if include_missing:
        condition = condition | (expression.is_(None))
    return statement.having(condition)


def _has_missing(row: dict[str, object]) -> bool:
    return any(row.get(key) is None for key in DISPLAY_METRICS)


def _valuation_status(row: dict[str, object]) -> str:
    if row.get("pe_ttm") is not None or row.get("ev_ebitda") is not None or row.get("fcf_yield") is not None:
        return "available"
    return "insufficient_data"


def _market_exchanges(market: str) -> list[str]:
    if market.upper() in {"CN", "A_SHARE", "CHINA"}:
        return ["SSE", "SZSE", "BSE"]
    return [market.upper()]


def _board_prefixes(board: str) -> list[str]:
    normalized = board.lower()
    if normalized in {"star", "sse_star"}:
        return ["688"]
    if normalized in {"chinext", "szse_chinext"}:
        return ["3"]
    if normalized in {"bse"}:
        return ["8", "4"]
    return []


def _preset_dict(preset: ScreenPreset) -> dict[str, object]:
    return {
        "id": preset.id,
        "name": preset.name,
        "filters": preset.filters_json,
        "created_by": preset.created_by,
        "created_at": preset.created_at.isoformat() if preset.created_at else None,
    }
