from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from finresearch.api.dependencies import library_path
from finresearch.metrics import CalculationContext, MetricResult, list_metric_definitions
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.metric_calculation import MetricCalculationService


router = APIRouter()


@router.get("/{symbol}/financials")
def get_financials(
    symbol: str,
    years: int = 5,
    as_of: str | None = None,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return FinancialFactRepository(db_path).list_by_symbol(symbol, years=years, as_of_date=as_of)


@router.get("/{symbol}/metrics")
def get_metrics(
    symbol: str,
    years: int = 5,
    as_of: str | None = None,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    fact_repo = FinancialFactRepository(db_path)
    periods = tuple(
        fact_repo.periods(
            symbol,
            years=years,
            as_of_date=as_of,
            strict_as_of=as_of is not None,
        )
    )
    latest_currency = next((period.currency for period in periods if period.currency), None)
    prices = tuple(PriceRepository(db_path).price_series(symbol, end_date=as_of, limit=260))
    context = CalculationContext(
        financial_periods=periods,
        price_series=prices,
        as_of_date=as_of,
        strict_as_of=as_of is not None,
        currency=latest_currency,
    )
    results = MetricCalculationService().calculate(context, symbol=symbol)
    definitions = {definition.code: definition for definition in list_metric_definitions()}
    return [_metric_result_dict(result, definitions) for result in results]


def _metric_result_dict(
    result: MetricResult,
    definitions: dict[str, object],
) -> dict[str, object]:
    definition = definitions.get(result.code)
    return {
        "code": result.code,
        "implementation_status": getattr(definition, "implementation_status", "not_available"),
        "calculation_domain": getattr(definition, "calculation_domain", None),
        "value": result.value,
        "quality_status": result.quality_status,
        "missing_reason": result.missing_reason,
        "formula": result.formula or getattr(definition, "formula", ""),
        "inputs": result.input_values,
        "source_fact_ids": list(result.source_fact_ids),
        "source_urls": list(result.source_urls),
        "source_price_ids": list(result.source_price_ids),
        "warnings": list(result.warnings),
        "period_start": result.period_start,
        "period_end": result.period_end,
        "as_of": result.as_of,
        "currency": result.currency,
        "unit": result.unit,
        "price_source": result.price_source,
        "data_source": result.price_source,
        "selected_source_reason": result.selected_source_reason,
        "benchmark_code": result.benchmark_code,
        "benchmark_source": result.benchmark_source,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "observations_count": result.observations_count,
        "adjustment_type": result.adjustment_type,
        "assumptions": result.assumptions,
        "calculation_version": result.formula_version,
    }
