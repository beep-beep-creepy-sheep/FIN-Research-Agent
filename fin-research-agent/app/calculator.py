from __future__ import annotations

from app.models import FinancialInputs


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def calculate_ratios(data: FinancialInputs) -> dict[str, float | None]:
    average_equity = None
    if data.equity_begin is not None and data.equity_end is not None:
        average_equity = (data.equity_begin + data.equity_end) / 2

    free_cash_flow = None
    if data.operating_cash_flow is not None and data.capital_expenditure is not None:
        free_cash_flow = data.operating_cash_flow - data.capital_expenditure

    net_debt = None
    if data.interest_bearing_debt is not None and data.cash is not None:
        net_debt = data.interest_bearing_debt - data.cash

    return {
        "gross_margin": _safe_div(data.gross_profit, data.revenue),
        "net_margin": _safe_div(data.net_profit, data.revenue),
        "cash_conversion": _safe_div(data.operating_cash_flow, data.net_profit),
        "roe": _safe_div(data.net_profit, average_equity),
        "free_cash_flow": free_cash_flow,
        "net_debt": net_debt,
    }
