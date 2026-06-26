from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from finresearch.metrics.context import CalculationContext, FinancialPeriod, MetricResult
from finresearch.metrics.definitions import (
    METRIC_FORMULAS,
    MetricDefinition,
    list_metric_definitions,
)
from finresearch.services.price_analytics import (
    PRICE_METRIC_CODES,
    PriceAnalyticsService,
    select_canonical_price_series,
)
from finresearch.services.professional_metrics import ProfessionalMetricEngine
from finresearch.settings import get_settings


PROFESSIONAL_METRIC_CODES = frozenset(
    {
        "revenue_ttm",
        "net_profit_ttm",
        "revenue_yoy",
        "net_profit_yoy",
        "fcf_ttm",
        "ebitda_ttm",
        "net_debt",
        "enterprise_value",
        "fcf_yield",
        "net_debt_to_ebitda",
        "ev_to_ebitda",
        "pe_ttm",
        "roic",
    }
)
LEGACY_FORMULA_CODES = frozenset(METRIC_FORMULAS)
PRICE_HANDLER_CODES = frozenset(PRICE_METRIC_CODES)
EXECUTABLE_HANDLER_CODES = PROFESSIONAL_METRIC_CODES | LEGACY_FORMULA_CODES | PRICE_HANDLER_CODES

REGISTERED_DEFINITION_COUNT = len(list_metric_definitions())
EXECUTABLE_HANDLER_COUNT = len(EXECUTABLE_HANDLER_CODES)
API_EXPOSED_METRIC_COUNT = REGISTERED_DEFINITION_COUNT
IMPLEMENTED_METRIC_COUNT = len(
    [
        definition
        for definition in list_metric_definitions()
        if definition.implementation_status == "implemented"
        and definition.code in EXECUTABLE_HANDLER_CODES
    ]
)


class MetricCalculationService:
    def __init__(self) -> None:
        self.professional_engine = ProfessionalMetricEngine()
        self.price_analytics = PriceAnalyticsService()

    def calculate(self, context: CalculationContext, *, symbol: str) -> list[MetricResult]:
        settings = get_settings()
        canonical = select_canonical_price_series(
            context.price_series,
            symbol=symbol,
            adjustment_type=settings.cn_stock_adjustment_type,
            source_priority=settings.price_source_priority,
        )
        calculation_context = replace(context, price_series=canonical.prices)

        professional_results = {
            result.code: _with_price_policy(result, canonical)
            for result in self.professional_engine.calculate(calculation_context)
        }
        legacy_results = {
            result.code: result
            for result in _legacy_results(context.financial_periods, context)
        }
        price_results = {
            result.code: _with_price_policy(result, canonical)
            for result in self._price_results(calculation_context, canonical.missing_reason)
        }

        output: list[MetricResult] = []
        for definition in list_metric_definitions():
            if definition.code not in EXECUTABLE_HANDLER_CODES:
                output.append(_missing_result(definition, "no_executable_handler", context))
                continue
            if definition.code in professional_results:
                output.append(professional_results[definition.code])
            elif definition.code in PRICE_HANDLER_CODES:
                output.append(price_results.get(definition.code) or _missing_result(definition, "missing_price_series", context))
            else:
                output.append(legacy_results.get(definition.code) or _missing_result(definition, "missing_structured_financial_facts", context))
        return output

    def _price_results(
        self,
        context: CalculationContext,
        canonical_missing_reason: str | None,
    ) -> list[MetricResult]:
        if canonical_missing_reason is not None:
            return [
                MetricResult(
                    code=code,
                    value=None,
                    quality_status="missing",
                    missing_reason=canonical_missing_reason,
                    observations_count=0,
                    adjustment_type=get_settings().cn_stock_adjustment_type,
                )
                for code in PRICE_METRIC_CODES
            ]
        return self.price_analytics.calculate(
            context.price_series,
            context.benchmark_series,
            benchmark_code=context.benchmark_code,
            trading_days_per_year=context.trading_days_per_year,
            risk_free_rate=context.risk_free_rate,
        )


def _legacy_results(periods: tuple[FinancialPeriod, ...], context: CalculationContext) -> list[MetricResult]:
    if not periods:
        return []

    results: list[MetricResult] = []
    latest = _latest_compatible_period(periods)
    previous = _previous_compatible_period(latest, periods) if latest else None
    missing_reason = _period_set_missing_reason(periods, latest)
    if missing_reason == "currency_mismatch":
        return [
            _missing_result(definition, missing_reason, context)
            for definition in list_metric_definitions()
            if definition.code in LEGACY_FORMULA_CODES
        ]
    ordered = sorted(
        [period for period in periods if latest and _same_reporting_basis(period, latest)],
        key=lambda period: period.period_end,
    )

    for definition in list_metric_definitions():
        if definition.code not in LEGACY_FORMULA_CODES:
            continue
        if latest is None:
            results.append(_missing_result(definition, missing_reason or "missing_compatible_period", context))
            continue
        required_previous = _requires_previous_period(definition.code)
        if required_previous and previous is None:
            results.append(_legacy_missing(definition, latest, context, "missing_compatible_prior_period"))
            continue
        value, reason = METRIC_FORMULAS[definition.code](
            _period_row(latest),
            _period_row(previous) if previous else None,
            [_period_row(period) for period in ordered],
        )
        lineage = _legacy_lineage(definition.code, latest, previous)
        if reason is None and not lineage["source_fact_ids"]:
            reason = "missing_source_fact_lineage"
            value = None
        results.append(
            MetricResult(
                code=definition.code,
                value=value,
                period_start=latest.period_start,
                period_end=latest.period_end,
                as_of=latest.publication_date or context.as_of_date,
                unit=definition.unit,
                formula=definition.formula,
                formula_version=definition.calculation_version,
                input_values=lineage["input_values"],
                source_fact_ids=lineage["source_fact_ids"],
                source_urls=lineage["source_urls"],
                quality_status="missing" if reason else "calculated",
                missing_reason=reason,
                currency=latest.currency or context.currency,
            )
        )
    return results


def _period_row(period: FinancialPeriod) -> dict[str, object]:
    return {
        "period_end": period.period_end,
        "currency": period.currency,
        **period.values,
    }


def _latest_compatible_period(periods: tuple[FinancialPeriod, ...]) -> FinancialPeriod | None:
    compatible = [period for period in periods if period.currency and period.statement_scope and period.report_type]
    if not compatible:
        return None
    return sorted(compatible, key=lambda period: (period.period_end, period.publication_date or ""))[-1]


def _previous_compatible_period(
    latest: FinancialPeriod | None,
    periods: tuple[FinancialPeriod, ...],
) -> FinancialPeriod | None:
    if latest is None or latest.period_start is None:
        return None
    candidates = [
        period
        for period in periods
        if period.period_end < latest.period_end
        and _same_reporting_basis(period, latest)
        and _ends_immediately_before(period, latest)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda period: (period.period_end, period.publication_date or ""))[-1]


def _same_reporting_basis(left: FinancialPeriod, right: FinancialPeriod) -> bool:
    return (
        left.currency == right.currency
        and left.report_type == right.report_type
        and left.statement_scope == right.statement_scope
        and left.is_consolidated == right.is_consolidated
        and left.flow_basis == right.flow_basis
    )


def _ends_immediately_before(previous: FinancialPeriod, latest: FinancialPeriod) -> bool:
    if latest.period_start is None:
        return False
    try:
        return date.fromisoformat(previous.period_end) == date.fromisoformat(latest.period_start) - timedelta(days=1)
    except ValueError:
        return False


def _period_set_missing_reason(
    periods: tuple[FinancialPeriod, ...],
    latest: FinancialPeriod | None,
) -> str | None:
    if latest is None:
        currencies = {period.currency for period in periods if period.currency}
        if len(currencies) > 1:
            return "currency_mismatch"
        return "missing_compatible_period"
    if any(period.currency and period.currency != latest.currency for period in periods):
        return "currency_mismatch"
    if any(period.report_type and period.report_type != latest.report_type for period in periods):
        return "incompatible_report_type"
    if any(period.statement_scope and period.statement_scope != latest.statement_scope for period in periods):
        return "incompatible_statement_scope"
    return None


def _requires_previous_period(code: str) -> bool:
    return code in {
        "roe",
        "roa",
        "asset_turnover",
        "equity_multiplier",
        "receivable_days",
        "inventory_days",
        "payable_days",
        "cash_conversion_cycle",
    }


def _legacy_lineage(
    code: str,
    latest: FinancialPeriod,
    previous: FinancialPeriod | None,
) -> dict[str, object]:
    latest_codes, previous_codes = _legacy_input_codes(code, latest, previous)
    fact_ids = _fact_ids_for(latest, latest_codes)
    urls = _urls_for(latest, latest_codes)
    input_values: dict[str, object] = {
        "latest": _values_for(latest, latest_codes),
        "latest_period_start": latest.period_start,
        "latest_period_end": latest.period_end,
        "latest_publication_date": latest.publication_date,
        "report_type": latest.report_type,
        "statement_scope": latest.statement_scope,
        "flow_basis": latest.flow_basis,
    }
    if previous and previous_codes:
        fact_ids += _fact_ids_for(previous, previous_codes)
        urls += _urls_for(previous, previous_codes)
        input_values["previous"] = _values_for(previous, previous_codes)
        input_values["previous_period_start"] = previous.period_start
        input_values["previous_period_end"] = previous.period_end
        input_values["previous_publication_date"] = previous.publication_date
    return {
        "source_fact_ids": tuple(dict.fromkeys(fact_ids)),
        "source_urls": tuple(dict.fromkeys(urls)),
        "input_values": input_values,
    }


def _legacy_input_codes(
    code: str,
    latest: FinancialPeriod,
    previous: FinancialPeriod | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    simple_inputs = {
        "fcf": (("operating_cash_flow", "capital_expenditure"), ()),
        "fcf_margin": (("operating_cash_flow", "capital_expenditure", "revenue"), ()),
        "net_debt": (_present_codes(latest, ("interest_bearing_debt", "total_debt", "cash", "cash_and_equivalents")), ()),
        "net_debt_to_equity": (_present_codes(latest, ("interest_bearing_debt", "total_debt", "cash", "cash_and_equivalents", "total_equity", "equity_parent")), ()),
        "quick_ratio": (_present_codes(latest, ("current_assets", "inventory", "current_liabilities")), ()),
        "working_capital_to_revenue": (_present_codes(latest, ("current_assets", "current_liabilities", "revenue")), ()),
        "pe": (_present_codes(latest, ("market_cap", "net_profit_parent", "net_profit")), ()),
        "roic_proxy": (_present_codes(latest, ("operating_profit", "income_tax", "profit_before_tax", "total_assets", "cash", "cash_and_equivalents", "current_liabilities")), ()),
    }
    if code in simple_inputs:
        return simple_inputs[code]
    if code == "cash_conversion_cycle":
        balance_codes = _present_codes(latest, ("accounts_receivable", "inventory", "accounts_payable"))
        flow_codes = _present_codes(latest, ("revenue", "cost_of_goods_sold"))
        return balance_codes + flow_codes, _present_codes(previous, ("accounts_receivable", "inventory", "accounts_payable"))
    if code in {"receivable_days", "inventory_days", "payable_days"}:
        balance_by_code: dict[str, tuple[str, ...]] = {
            "receivable_days": ("accounts_receivable",),
            "inventory_days": ("inventory",),
            "payable_days": ("accounts_payable",),
        }
        flow_by_code: dict[str, tuple[str, ...]] = {
            "receivable_days": ("revenue",),
            "inventory_days": ("cost_of_goods_sold",),
            "payable_days": ("cost_of_goods_sold",),
        }
        balance = balance_by_code[code]
        return _present_codes(latest, balance + flow_by_code[code]), _present_codes(previous, balance)
    if code in {"roe", "roa", "asset_turnover", "equity_multiplier"}:
        numerator_by_code: dict[str, tuple[str, ...]] = {
            "roe": ("net_profit", "net_profit_parent"),
            "roa": ("net_profit", "net_profit_parent"),
            "asset_turnover": ("revenue",),
            "equity_multiplier": (),
        }
        turnover_balance_by_code: dict[str, tuple[str, ...]] = {
            "roe": ("total_equity", "equity_parent"),
            "roa": ("total_assets",),
            "asset_turnover": ("total_assets",),
            "equity_multiplier": ("total_assets", "total_equity", "equity_parent"),
        }
        latest_inputs = _present_codes(latest, numerator_by_code[code] + turnover_balance_by_code[code])
        return latest_inputs, _present_codes(previous, turnover_balance_by_code[code])
    definition = next(item for item in list_metric_definitions() if item.code == code)
    return _present_codes(latest, definition.inputs), ()


def _present_codes(period: FinancialPeriod | None, codes: tuple[str, ...]) -> tuple[str, ...]:
    if period is None:
        return ()
    return tuple(code for code in codes if period.value(code) is not None)


def _fact_ids_for(period: FinancialPeriod, codes: tuple[str, ...]) -> tuple[int, ...]:
    ids: list[int] = []
    for code in codes:
        ids.extend(period.fact_ids_by_metric.get(code, ()))
    return tuple(ids)


def _urls_for(period: FinancialPeriod, codes: tuple[str, ...]) -> tuple[str, ...]:
    urls: list[str] = []
    for code in codes:
        urls.extend(period.source_urls_by_metric.get(code, ()))
    return tuple(urls)


def _values_for(period: FinancialPeriod, codes: tuple[str, ...]) -> dict[str, float]:
    return {code: period.values[code] for code in codes if code in period.values}


def _legacy_missing(
    definition: MetricDefinition,
    period: FinancialPeriod,
    context: CalculationContext,
    reason: str,
) -> MetricResult:
    return MetricResult(
        code=definition.code,
        value=None,
        period_start=period.period_start,
        period_end=period.period_end,
        as_of=period.publication_date or context.as_of_date,
        currency=period.currency or context.currency,
        unit=definition.unit,
        formula=definition.formula,
        formula_version=definition.calculation_version,
        quality_status="missing",
        missing_reason=reason,
    )


def _missing_result(definition: MetricDefinition, reason: str, context: CalculationContext) -> MetricResult:
    return MetricResult(
        code=definition.code,
        value=None,
        as_of=context.as_of_date,
        currency=context.currency,
        unit=definition.unit,
        formula=definition.formula,
        formula_version=definition.calculation_version,
        quality_status="missing",
        missing_reason=reason,
    )


def _with_price_policy(result: MetricResult, canonical: object) -> MetricResult:
    adjustment_type = getattr(canonical, "adjustment_type", None)
    data_source = getattr(canonical, "data_source", None)
    reason = getattr(canonical, "selected_source_reason", None)
    if result.missing_reason == "missing_market_cap" and getattr(canonical, "missing_reason", None):
        result = replace(result, missing_reason=getattr(canonical, "missing_reason"))
    return replace(
        result,
        adjustment_type=result.adjustment_type or adjustment_type,
        price_source=result.price_source or data_source,
        selected_source_reason=reason or result.selected_source_reason,
        observations_count=result.observations_count if result.observations_count is not None else getattr(canonical, "observations_count", None),
    )
