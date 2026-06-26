from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FinancialPeriod:
    symbol: str
    period_start: str | None
    period_end: str
    publication_date: str | None
    report_type: str | None
    statement_type: str | None
    statement_scope: str | None
    is_consolidated: bool
    currency: str | None
    unit: str | None
    data_source: str | None
    quality_status: str | None
    version: int | None
    fact_ids_by_metric: dict[str, tuple[int, ...]]
    source_urls_by_metric: dict[str, tuple[str, ...]]
    source_pages_by_metric: dict[str, tuple[int, ...]]
    values: dict[str, float]
    flow_basis: str | None = None
    is_cumulative: bool | None = None
    source_flow_basis: str | None = None

    def value(self, *codes: str) -> float | None:
        for code in codes:
            if code in self.values:
                return self.values[code]
        return None

    def fact_ids(self, *codes: str) -> tuple[int, ...]:
        ids: list[int] = []
        for code in codes:
            ids.extend(self.fact_ids_by_metric.get(code, ()))
        return tuple(dict.fromkeys(ids))

    def source_urls(self, *codes: str) -> tuple[str, ...]:
        urls: list[str] = []
        for code in codes:
            urls.extend(self.source_urls_by_metric.get(code, ()))
        return tuple(dict.fromkeys(urls))


@dataclass(frozen=True)
class FinancialSeries:
    symbol: str
    periods: tuple[FinancialPeriod, ...]


@dataclass(frozen=True)
class PricePoint:
    id: int | None
    symbol: str
    trade_date: str
    close: float
    adjustment_type: str
    data_source: str


@dataclass(frozen=True)
class MarketInputContext:
    price_series: tuple[PricePoint, ...] = ()
    adjustment_type: str = "qfq"


@dataclass(frozen=True)
class BenchmarkInputContext:
    benchmark_code: str | None = None
    benchmark_series: tuple[PricePoint, ...] = ()
    data_source: str | None = None


@dataclass(frozen=True)
class CalculationContext:
    financial_periods: tuple[FinancialPeriod, ...] = ()
    price_series: tuple[PricePoint, ...] = ()
    benchmark_series: tuple[PricePoint, ...] = ()
    benchmark_code: str | None = None
    as_of_date: str | None = None
    strict_as_of: bool = False
    currency: str | None = None
    trading_days_per_year: int = 252
    risk_free_rate: float = 0.0
    industry: str | None = None
    calculation_version: str = "2.0.0"


@dataclass(frozen=True)
class MetricResult:
    code: str
    value: float | None
    period_start: str | None = None
    period_end: str | None = None
    as_of: str | None = None
    currency: str | None = None
    unit: str = "ratio"
    formula: str = ""
    formula_version: str = "2.0.0"
    input_values: dict[str, object] = field(default_factory=dict)
    source_fact_ids: tuple[int, ...] = ()
    source_urls: tuple[str, ...] = ()
    source_price_ids: tuple[int, ...] = ()
    price_source: str | None = None
    benchmark_code: str | None = None
    benchmark_source: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    observations_count: int | None = None
    adjustment_type: str | None = None
    assumptions: dict[str, object] = field(default_factory=dict)
    quality_status: str = "calculated"
    warnings: tuple[str, ...] = ()
    missing_reason: str | None = None


FLOW_METRICS = {
    "revenue",
    "gross_profit",
    "operating_profit",
    "ebit",
    "ebitda",
    "net_profit",
    "net_profit_parent",
    "operating_cash_flow",
    "capital_expenditure",
    "depreciation",
    "amortization",
    "income_tax",
    "profit_before_tax",
    "interest_expense",
    "cost_of_goods_sold",
    "cash_dividends",
}
