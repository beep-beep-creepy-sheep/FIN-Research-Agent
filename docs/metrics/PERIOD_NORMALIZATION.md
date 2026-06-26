# Period Normalization

Updated: 2026-06-26

## Contract

`FinancialPeriod` is the typed input contract for professional metrics. It preserves:

- symbol, period_start, period_end, publication_date
- report_type, statement_type, statement_scope, is_consolidated
- currency, unit, data_source, quality_status, version
- fact_ids_by_metric, source_urls_by_metric, source_pages_by_metric
- values

`CalculationContext` wraps financial periods, price series, benchmark series, as_of settings, currency, industry, risk-free assumptions, trading-day assumptions, and calculation version.

## Source Selection

`FinancialFactRepository.periods()` keeps the legacy matrix path compatible while also producing typed periods. When multiple facts exist for the same period and metric, the repository chooses by:

1. current version first
2. highest version number
3. lowest source priority value

When `strict_as_of=True`, facts with empty publication dates or publication dates after `as_of_date` are excluded.

## Cumulative-To-Quarter Rules

For flow metrics such as revenue, net profit, EBIT, OCF, capex, depreciation, amortization, interest, and COGS:

- Q1 single quarter = Q1 cumulative
- Q2 single quarter = half-year cumulative - Q1 cumulative
- Q3 single quarter = nine-month cumulative - half-year cumulative
- Q4 single quarter = annual cumulative - nine-month cumulative

Point-in-time metrics such as cash, debt, equity, shares, and market cap are copied from the selected period.

## TTM

TTM uses exactly four contiguous comparable normalized quarters. If Q2 or Q3 is missing, the service returns:

`missing_reason: insufficient_contiguous_quarters`

The service does not add annual revenue and Q4 together, and it does not treat half-year or nine-month cumulative values as single quarters.

Composite TTM metrics use `select_common_ttm_window(quarters, required_metric_codes, as_of_period_end)`. The selected window must contain the exact same four contiguous `QuarterKey` values for every required component:

- FCF TTM requires `operating_cash_flow` and `capital_expenditure`.
- EBITDA TTM uses direct `ebitda` when a common direct window exists; otherwise it requires `ebit`, `depreciation`, and `amortization` in the same window.
- ROIC first tries to align `ebit`, `income_tax`, and `profit_before_tax` in the same window. If tax components are unavailable or misaligned but EBIT has a valid four-quarter window, ROIC uses the EBIT window and records a tax-rate assumption warning instead of mixing tax periods.

When no shared four-quarter window exists, composite metrics return `insufficient_common_ttm_window` or `misaligned_ttm_components`. Result `input_values` include `selected_quarters`, `period_start`, and `period_end`; PE TTM and FCF Yield inherit the selected window from their underlying TTM metric.

## YoY

YoY compares comparable periods:

- annual report to prior annual report when annual periods exist
- otherwise the latest normalized quarter to the same quarter in the prior year

Missing comparable periods return `missing_comparable_period`; zero prior denominator returns `zero_denominator`.

## Lineage

Each normalized quarter carries source fact IDs, source URLs, and a conversion formula per metric. Professional metric results carry those IDs into `MetricResult.source_fact_ids` and API output.

## Tests

Coverage lives in:

- `backend/tests/test_period_normalization.py`
- `backend/tests/test_professional_metrics.py`

The tests cover cumulative conversion, contiguous TTM, common component windows, latest-quarter component gaps, older common windows, missing common windows, strict as_of common windows, annual comparable YoY, currency conflict, restatement precedence, source IDs, and future price exclusion.
