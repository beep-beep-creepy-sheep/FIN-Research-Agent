from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean


@dataclass(frozen=True)
class MetricDefinition:
    code: str
    name_en: str
    name_zh: str
    category: str
    formula: str
    inputs: tuple[str, ...]
    unit: str
    periodicity: str
    source_requirement: str
    applicable_industries: tuple[str, ...] = ("all",)
    caveats: str = ""
    calculation_version: str = "1.0.0"
    missing_behavior: str = "mark_missing"


@dataclass(frozen=True)
class MetricObservation:
    code: str
    value: float | None
    period_end: str | None
    as_of: str | None
    unit: str
    formula: str
    formula_version: str
    inputs: tuple[str, ...]
    source_fact_ids: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()
    missing_reason: str | None = None
    quality_status: str = "calculated"


MetricFunction = callable


def list_metric_definitions() -> list[MetricDefinition]:
    return list(METRIC_DEFINITIONS)


def get_metric_definition(code: str) -> MetricDefinition | None:
    return METRIC_DEFINITION_BY_CODE.get(code)


def calculate_registered_metrics(matrix: list[dict[str, object]]) -> list[MetricObservation]:
    if not matrix:
        return [
            _missing_observation(definition, None, "missing_structured_financial_facts")
            for definition in METRIC_DEFINITIONS
        ]
    currencies = {str(row["currency"]) for row in matrix if row.get("currency")}
    if len(currencies) > 1:
        period = _period(sorted(matrix, key=lambda row: str(row.get("period_end") or ""))[-1])
        return [
            _missing_observation(definition, period, "currency_mismatch")
            for definition in METRIC_DEFINITIONS
        ]
    ordered = sorted(matrix, key=lambda row: str(row.get("period_end") or ""))
    latest = ordered[-1]
    previous = ordered[-2] if len(ordered) > 1 else None
    observations: list[MetricObservation] = []
    for definition in METRIC_DEFINITIONS:
        value, reason = METRIC_FORMULAS[definition.code](latest, previous, ordered)
        observations.append(
            MetricObservation(
                code=definition.code,
                value=value,
                period_end=_period(latest),
                as_of=_period(latest),
                unit=definition.unit,
                formula=definition.formula,
                formula_version=definition.calculation_version,
                inputs=definition.inputs,
                missing_reason=reason,
                quality_status="missing" if reason else "calculated",
            )
        )
    return observations


def available_metric_values(matrix: list[dict[str, object]]) -> dict[str, float]:
    return {
        observation.code: observation.value
        for observation in calculate_registered_metrics(matrix)
        if observation.value is not None
    }


def metric_quality_flags(observations: list[MetricObservation]) -> list[str]:
    flags: list[str] = []
    values = {observation.code: observation.value for observation in observations}
    ocf_to_net_profit = values.get("ocf_to_net_profit")
    if ocf_to_net_profit is not None and ocf_to_net_profit < 1:
        flags.append("operating_cash_flow_below_net_profit")
    return flags


def _definition(
    code: str,
    name_en: str,
    name_zh: str,
    category: str,
    formula: str,
    inputs: tuple[str, ...],
    unit: str = "ratio",
    periodicity: str = "latest_period",
    source_requirement: str = "structured_financial_facts",
) -> MetricDefinition:
    return MetricDefinition(
        code=code,
        name_en=name_en,
        name_zh=name_zh,
        category=category,
        formula=formula,
        inputs=inputs,
        unit=unit,
        periodicity=periodicity,
        source_requirement=source_requirement,
        caveats="Uses available structured fields only; returns null with a missing reason instead of imputing values.",
    )


METRIC_DEFINITIONS = [
    _definition("revenue", "Revenue", "营业收入", "scale", "revenue", ("revenue",), "currency"),
    _definition("revenue_yoy", "Revenue YoY", "收入同比", "growth", "revenue / prior_revenue - 1", ("revenue",)),
    _definition("revenue_cagr_3y", "Revenue 3Y CAGR", "收入三年复合增速", "growth", "(latest / oldest) ** (1 / years) - 1", ("revenue",)),
    _definition("gross_profit", "Gross Profit", "毛利润", "profitability", "gross_profit", ("gross_profit",), "currency"),
    _definition("operating_profit", "Operating Profit", "营业利润", "profitability", "operating_profit", ("operating_profit",), "currency"),
    _definition("net_profit", "Net Profit", "净利润", "profitability", "net_profit or net_profit_parent", ("net_profit", "net_profit_parent"), "currency"),
    _definition("net_profit_yoy", "Net Profit YoY", "净利润同比", "growth", "net_profit / prior_net_profit - 1", ("net_profit", "net_profit_parent")),
    _definition("gross_margin", "Gross Margin", "毛利率", "profitability", "gross_profit / revenue", ("gross_profit", "revenue")),
    _definition("operating_margin", "Operating Margin", "营业利润率", "profitability", "operating_profit / revenue", ("operating_profit", "revenue")),
    _definition("net_margin", "Net Margin", "净利率", "profitability", "net_profit / revenue", ("net_profit", "net_profit_parent", "revenue")),
    _definition("ocf_margin", "Operating Cash Flow Margin", "经营现金流率", "cash_flow", "operating_cash_flow / revenue", ("operating_cash_flow", "revenue")),
    _definition("fcf", "Free Cash Flow", "自由现金流", "cash_flow", "operating_cash_flow - capital_expenditure", ("operating_cash_flow", "capital_expenditure"), "currency"),
    _definition("fcf_margin", "Free Cash Flow Margin", "自由现金流率", "cash_flow", "free_cash_flow / revenue", ("operating_cash_flow", "capital_expenditure", "revenue")),
    _definition("ocf_to_net_profit", "OCF / Net Profit", "经营现金流/净利润", "cash_flow", "operating_cash_flow / net_profit", ("operating_cash_flow", "net_profit", "net_profit_parent"), "multiple"),
    _definition("capex_intensity", "Capex Intensity", "资本开支强度", "cash_flow", "capital_expenditure / revenue", ("capital_expenditure", "revenue")),
    _definition("roe", "Return on Equity", "净资产收益率", "returns", "net_profit / average_equity", ("net_profit", "net_profit_parent", "total_equity")),
    _definition("roe_proxy", "ROE Proxy", "ROE 近似值", "returns", "net_profit / latest_equity", ("net_profit", "net_profit_parent", "total_equity")),
    _definition("roa", "Return on Assets", "资产收益率", "returns", "net_profit / average_assets", ("net_profit", "net_profit_parent", "total_assets")),
    _definition("roic_proxy", "ROIC Proxy", "投入资本回报率近似值", "returns", "operating_profit * (1 - tax_rate) / invested_capital", ("operating_profit", "income_tax", "total_assets", "cash", "current_liabilities")),
    _definition("asset_turnover", "Asset Turnover", "资产周转率", "du_pont", "revenue / average_assets", ("revenue", "total_assets"), "multiple"),
    _definition("equity_multiplier", "Equity Multiplier", "权益乘数", "du_pont", "average_assets / average_equity", ("total_assets", "total_equity"), "multiple"),
    _definition("liability_ratio", "Liability Ratio", "资产负债率", "leverage", "total_liabilities / total_assets", ("total_liabilities", "total_assets")),
    _definition("debt_to_equity", "Debt / Equity", "负债权益比", "leverage", "total_liabilities / total_equity", ("total_liabilities", "total_equity"), "multiple"),
    _definition("net_debt", "Net Debt", "净债务", "leverage", "interest_bearing_debt - cash", ("interest_bearing_debt", "cash"), "currency"),
    _definition("net_debt_to_equity", "Net Debt / Equity", "净债务权益比", "leverage", "net_debt / total_equity", ("interest_bearing_debt", "cash", "total_equity"), "multiple"),
    _definition("interest_coverage", "Interest Coverage", "利息覆盖倍数", "leverage", "operating_profit / interest_expense", ("operating_profit", "interest_expense"), "multiple"),
    _definition("cash_ratio", "Cash Ratio", "现金比率", "liquidity", "cash / current_liabilities", ("cash", "current_liabilities")),
    _definition("current_ratio", "Current Ratio", "流动比率", "liquidity", "current_assets / current_liabilities", ("current_assets", "current_liabilities"), "multiple"),
    _definition("quick_ratio", "Quick Ratio", "速动比率", "liquidity", "(current_assets - inventory) / current_liabilities", ("current_assets", "inventory", "current_liabilities"), "multiple"),
    _definition("receivable_days", "Receivable Days", "应收账款周转天数", "working_capital", "average_receivables / revenue * days", ("accounts_receivable", "revenue"), "days"),
    _definition("inventory_days", "Inventory Days", "存货周转天数", "working_capital", "average_inventory / cost_of_goods_sold * days", ("inventory", "cost_of_goods_sold"), "days"),
    _definition("payable_days", "Payable Days", "应付账款周转天数", "working_capital", "average_payables / cost_of_goods_sold * days", ("accounts_payable", "cost_of_goods_sold"), "days"),
    _definition("cash_conversion_cycle", "Cash Conversion Cycle", "现金周转周期", "working_capital", "receivable_days + inventory_days - payable_days", ("accounts_receivable", "inventory", "accounts_payable", "revenue", "cost_of_goods_sold"), "days"),
    _definition("working_capital_to_revenue", "Working Capital / Revenue", "营运资本/收入", "working_capital", "(current_assets - current_liabilities) / revenue", ("current_assets", "current_liabilities", "revenue")),
    _definition("contract_liability_to_revenue", "Contract Liability / Revenue", "合同负债/收入", "working_capital", "contract_liabilities / revenue", ("contract_liabilities", "revenue")),
    _definition("eps", "EPS", "每股收益", "per_share", "net_profit_parent / shares_outstanding", ("net_profit_parent", "shares_outstanding"), "currency_per_share"),
    _definition("book_value_per_share", "Book Value / Share", "每股净资产", "per_share", "equity_parent / shares_outstanding", ("equity_parent", "shares_outstanding"), "currency_per_share"),
    _definition("dividend_payout", "Dividend Payout", "分红率", "capital_allocation", "cash_dividends / net_profit_parent", ("cash_dividends", "net_profit_parent")),
    _definition("pe", "P/E", "市盈率", "valuation", "market_cap / net_profit_parent", ("market_cap", "net_profit_parent"), "multiple", source_requirement="market_cap_and_financial_facts"),
    _definition("pb", "P/B", "市净率", "valuation", "market_cap / equity_parent", ("market_cap", "equity_parent"), "multiple", source_requirement="market_cap_and_financial_facts"),
    _definition("ps", "P/S", "市销率", "valuation", "market_cap / revenue", ("market_cap", "revenue"), "multiple", source_requirement="market_cap_and_financial_facts"),
]

METRIC_DEFINITION_BY_CODE = {definition.code: definition for definition in METRIC_DEFINITIONS}


def _period(row: dict[str, object] | None) -> str | None:
    if not row:
        return None
    value = row.get("period_end")
    return str(value) if value else None


def _number(row: dict[str, object] | None, *keys: str) -> float | None:
    if not row:
        return None
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if not isinstance(value, str | bytes | int | float):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        return number
    return None


def _safe_div(numerator: float | None, denominator: float | None) -> tuple[float | None, str | None]:
    if numerator is None:
        return None, "missing_numerator"
    if denominator is None:
        return None, "missing_denominator"
    if denominator == 0:
        return None, "zero_denominator"
    return numerator / denominator, None


def _identity(*keys: str):
    def calculate(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
        value = _number(latest, *keys)
        return (value, None) if value is not None else (None, "missing_input")

    return calculate


def _ratio(numerator_keys: tuple[str, ...], denominator_keys: tuple[str, ...]):
    def calculate(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
        return _safe_div(_number(latest, *numerator_keys), _number(latest, *denominator_keys))

    return calculate


def _yoy(keys: tuple[str, ...]):
    def calculate(latest: dict[str, object], previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
        latest_value = _number(latest, *keys)
        previous_value = _number(previous, *keys)
        value, reason = _safe_div(latest_value, previous_value)
        if reason or value is None:
            return None, reason
        return value - 1, None

    return calculate


def _average(latest: dict[str, object], previous: dict[str, object] | None, *keys: str) -> float | None:
    values = [_number(row, *keys) for row in (latest, previous) if row is not None]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return fmean(present)


def _ratio_to_average(numerator_keys: tuple[str, ...], denominator_keys: tuple[str, ...]):
    def calculate(latest: dict[str, object], previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
        return _safe_div(_number(latest, *numerator_keys), _average(latest, previous, *denominator_keys))

    return calculate


def _free_cash_flow(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    ocf = _number(latest, "operating_cash_flow")
    capex = _number(latest, "capital_expenditure")
    if ocf is None or capex is None:
        return None, "missing_input"
    return ocf - abs(capex), None


def _fcf_margin(latest: dict[str, object], previous: dict[str, object] | None, matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    fcf, reason = _free_cash_flow(latest, previous, matrix)
    if reason:
        return None, reason
    return _safe_div(fcf, _number(latest, "revenue"))


def _net_debt(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    debt = _number(latest, "interest_bearing_debt", "total_debt")
    cash = _number(latest, "cash", "cash_and_equivalents")
    if debt is None or cash is None:
        return None, "missing_input"
    return debt - cash, None


def _net_debt_to_equity(latest: dict[str, object], previous: dict[str, object] | None, matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    net_debt, reason = _net_debt(latest, previous, matrix)
    if reason:
        return None, reason
    return _safe_div(net_debt, _number(latest, "total_equity", "equity_parent"))


def _pe(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    earnings = _number(latest, "net_profit_parent", "net_profit")
    if earnings is not None and earnings <= 0:
        return None, "not_applicable_negative_earnings"
    return _safe_div(_number(latest, "market_cap"), earnings)


def _quick_ratio(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    current_assets = _number(latest, "current_assets")
    inventory = _number(latest, "inventory")
    current_liabilities = _number(latest, "current_liabilities")
    if current_assets is None or inventory is None:
        return None, "missing_numerator"
    return _safe_div(current_assets - inventory, current_liabilities)


def _working_capital_to_revenue(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    current_assets = _number(latest, "current_assets")
    current_liabilities = _number(latest, "current_liabilities")
    if current_assets is None or current_liabilities is None:
        return None, "missing_numerator"
    return _safe_div(current_assets - current_liabilities, _number(latest, "revenue"))


def _days(balance_keys: tuple[str, ...], flow_keys: tuple[str, ...]):
    def calculate(latest: dict[str, object], previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
        value, reason = _safe_div(_average(latest, previous, *balance_keys), _number(latest, *flow_keys))
        if reason or value is None:
            return None, reason
        return value * 365, None

    return calculate


def _cash_conversion_cycle(latest: dict[str, object], previous: dict[str, object] | None, matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    receivable, r_reason = _days(("accounts_receivable",), ("revenue",))(latest, previous, matrix)
    inventory, i_reason = _days(("inventory",), ("cost_of_goods_sold",))(latest, previous, matrix)
    payable, p_reason = _days(("accounts_payable",), ("cost_of_goods_sold",))(latest, previous, matrix)
    if r_reason or i_reason or p_reason:
        return None, "missing_input"
    return receivable + inventory - payable, None


def _revenue_cagr_3y(_latest: dict[str, object], _previous: dict[str, object] | None, matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    points = [(row.get("period_end"), _number(row, "revenue")) for row in matrix if _number(row, "revenue") is not None]
    if len(points) < 2:
        return None, "insufficient_history"
    first_period, first = points[0]
    last_period, last = points[-1]
    if not first or last is None or first <= 0:
        return None, "invalid_history"
    try:
        years = max(1, int(str(last_period)[:4]) - int(str(first_period)[:4]))
    except ValueError:
        years = len(points) - 1
    years = min(3, years) if years > 0 else 1
    return (last / first) ** (1 / years) - 1, None


def _roic_proxy(latest: dict[str, object], _previous: dict[str, object] | None, _matrix: list[dict[str, object]]) -> tuple[float | None, str | None]:
    operating_profit = _number(latest, "operating_profit")
    income_tax = _number(latest, "income_tax") or 0.0
    profit_before_tax = _number(latest, "profit_before_tax")
    total_assets = _number(latest, "total_assets")
    cash = _number(latest, "cash", "cash_and_equivalents") or 0.0
    current_liabilities = _number(latest, "current_liabilities") or 0.0
    if operating_profit is None or total_assets is None:
        return None, "missing_input"
    tax_rate = 0.0 if not profit_before_tax else max(0.0, min(0.35, income_tax / profit_before_tax))
    invested_capital = total_assets - cash - current_liabilities
    return _safe_div(operating_profit * (1 - tax_rate), invested_capital)


METRIC_FORMULAS = {
    "revenue": _identity("revenue"),
    "revenue_yoy": _yoy(("revenue",)),
    "revenue_cagr_3y": _revenue_cagr_3y,
    "gross_profit": _identity("gross_profit"),
    "operating_profit": _identity("operating_profit"),
    "net_profit": _identity("net_profit", "net_profit_parent"),
    "net_profit_yoy": _yoy(("net_profit", "net_profit_parent")),
    "gross_margin": _ratio(("gross_profit",), ("revenue",)),
    "operating_margin": _ratio(("operating_profit",), ("revenue",)),
    "net_margin": _ratio(("net_profit", "net_profit_parent"), ("revenue",)),
    "ocf_margin": _ratio(("operating_cash_flow",), ("revenue",)),
    "fcf": _free_cash_flow,
    "fcf_margin": _fcf_margin,
    "ocf_to_net_profit": _ratio(("operating_cash_flow",), ("net_profit", "net_profit_parent")),
    "capex_intensity": _ratio(("capital_expenditure",), ("revenue",)),
    "roe": _ratio_to_average(("net_profit", "net_profit_parent"), ("total_equity", "equity_parent")),
    "roe_proxy": _ratio(("net_profit", "net_profit_parent"), ("total_equity", "equity_parent")),
    "roa": _ratio_to_average(("net_profit", "net_profit_parent"), ("total_assets",)),
    "roic_proxy": _roic_proxy,
    "asset_turnover": _ratio_to_average(("revenue",), ("total_assets",)),
    "equity_multiplier": lambda latest, previous, _matrix: _safe_div(
        _average(latest, previous, "total_assets"),
        _average(latest, previous, "total_equity", "equity_parent"),
    ),
    "liability_ratio": _ratio(("total_liabilities",), ("total_assets",)),
    "debt_to_equity": _ratio(("total_liabilities",), ("total_equity", "equity_parent")),
    "net_debt": _net_debt,
    "net_debt_to_equity": _net_debt_to_equity,
    "interest_coverage": _ratio(("operating_profit",), ("interest_expense",)),
    "cash_ratio": _ratio(("cash", "cash_and_equivalents"), ("current_liabilities",)),
    "current_ratio": _ratio(("current_assets",), ("current_liabilities",)),
    "quick_ratio": _quick_ratio,
    "receivable_days": _days(("accounts_receivable",), ("revenue",)),
    "inventory_days": _days(("inventory",), ("cost_of_goods_sold",)),
    "payable_days": _days(("accounts_payable",), ("cost_of_goods_sold",)),
    "cash_conversion_cycle": _cash_conversion_cycle,
    "working_capital_to_revenue": _working_capital_to_revenue,
    "contract_liability_to_revenue": _ratio(("contract_liabilities",), ("revenue",)),
    "eps": _ratio(("net_profit_parent",), ("shares_outstanding",)),
    "book_value_per_share": _ratio(("equity_parent", "total_equity"), ("shares_outstanding",)),
    "dividend_payout": _ratio(("cash_dividends",), ("net_profit_parent", "net_profit")),
    "pe": _pe,
    "pb": _ratio(("market_cap",), ("equity_parent", "total_equity")),
    "ps": _ratio(("market_cap",), ("revenue",)),
}


def _missing_observation(definition: MetricDefinition, period: str | None, reason: str) -> MetricObservation:
    return MetricObservation(
        code=definition.code,
        value=None,
        period_end=period,
        as_of=period,
        unit=definition.unit,
        formula=definition.formula,
        formula_version=definition.calculation_version,
        inputs=definition.inputs,
        missing_reason=reason,
        quality_status="missing",
    )
