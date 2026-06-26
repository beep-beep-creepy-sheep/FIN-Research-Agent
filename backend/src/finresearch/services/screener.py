from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func, or_, select

from finresearch.database.models import Company, FinancialFact
from finresearch.database.session import session_scope


@dataclass(frozen=True)
class ScreenQuery:
    q: str | None = None
    industry: str | None = None
    min_revenue: float | None = None
    min_net_margin: float | None = None
    min_roe: float | None = None
    max_liability_ratio: float | None = None
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
        assets = _metric_expr("total_assets")
        liabilities = _metric_expr("total_liabilities")
        equity = _metric_expr("total_equity", "equity_parent")
        net_margin = net_profit / func.nullif(revenue, 0)
        roe = net_profit / func.nullif(equity, 0)
        liability_ratio = liabilities / func.nullif(assets, 0)

        statement = (
            select(
                Company.symbol,
                Company.company_name,
                Company.exchange,
                Company.industry,
                latest_period.c.period_end,
                revenue.label("revenue"),
                net_profit.label("net_profit"),
                net_margin.label("net_margin"),
                roe.label("roe"),
                liability_ratio.label("liability_ratio"),
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
        if request.min_revenue is not None:
            statement = statement.having(revenue >= request.min_revenue)
        if request.min_net_margin is not None:
            statement = statement.having(net_margin >= request.min_net_margin)
        if request.min_roe is not None:
            statement = statement.having(roe >= request.min_roe)
        if request.max_liability_ratio is not None:
            statement = statement.having(liability_ratio <= request.max_liability_ratio)
        sort_expr = _sort_expr(request.sort_by)
        statement = statement.order_by(
            sort_expr.asc() if request.sort_direction == "asc" else sort_expr.desc()
        ).offset(max(0, request.offset)).limit(max(1, min(request.limit, 200)))

        with session_scope() as session:
            rows = [dict(row._mapping) for row in session.execute(statement).all()]
        as_of_values = [str(row["period_end"]) for row in rows if row.get("period_end") is not None]
        return {
            "rows": rows,
            "count": len(rows),
            "offset": max(0, request.offset),
            "limit": max(1, min(request.limit, 200)),
            "as_of": max(as_of_values) if as_of_values else None,
            "updated_at": max(as_of_values) if as_of_values else None,
            "filters": request.__dict__,
            "data_quality": {
                "source": "financial_facts",
                "note": "筛选仅使用本地数据库最新财务期间；缺字段公司不会被强行补值。",
            },
        }


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
}
