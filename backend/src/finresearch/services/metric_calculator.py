from __future__ import annotations


def calculate_metric_signals(matrix: list[dict[str, object]]) -> dict[str, object]:
    if not matrix:
        return {"quality_flags": ["insufficient_structured_data"], "metrics": {}}

    latest = matrix[0]
    metrics: dict[str, float] = {}
    flags: list[str] = []

    revenue = _number(latest.get("revenue"))
    net_profit = _number(latest.get("net_profit") or latest.get("net_profit_parent"))
    operating_cash_flow = _number(latest.get("operating_cash_flow"))
    total_assets = _number(latest.get("total_assets"))
    total_liabilities = _number(latest.get("total_liabilities"))
    total_equity = _number(latest.get("total_equity"))

    if revenue and net_profit is not None:
        metrics["net_margin"] = net_profit / revenue
    if net_profit and operating_cash_flow is not None:
        metrics["cash_conversion"] = operating_cash_flow / net_profit
        if operating_cash_flow < net_profit:
            flags.append("operating_cash_flow_below_net_profit")
    if total_assets and total_liabilities is not None:
        metrics["liability_ratio"] = total_liabilities / total_assets
    if total_equity and net_profit is not None:
        metrics["roe_proxy"] = net_profit / total_equity

    return {"quality_flags": flags, "metrics": metrics}


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

