from __future__ import annotations

from dataclasses import replace

from finresearch.metrics.context import CalculationContext, FinancialPeriod, MetricResult
from finresearch.metrics.definitions import (
    METRIC_FORMULAS,
    MetricDefinition,
    calculate_registered_metrics,
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
    observations = calculate_registered_metrics([_period_row(period) for period in periods])
    return [
        MetricResult(
            code=observation.code,
            value=observation.value,
            period_end=observation.period_end,
            as_of=observation.as_of or context.as_of_date,
            unit=observation.unit,
            formula=observation.formula,
            formula_version=observation.formula_version,
            input_values={"inputs": observation.inputs},
            source_fact_ids=observation.source_fact_ids,
            quality_status=observation.quality_status,
            missing_reason=observation.missing_reason,
            currency=context.currency,
        )
        for observation in observations
        if observation.code in LEGACY_FORMULA_CODES
    ]


def _period_row(period: FinancialPeriod) -> dict[str, object]:
    return {
        "period_end": period.period_end,
        "currency": period.currency,
        **period.values,
    }


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
