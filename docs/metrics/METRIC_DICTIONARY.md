# Metric Dictionary

Updated: 2026-06-26

## Status Counts

- registered definitions: 66
- executable handler coverage: 66 unique metric codes
- API exposed metric results: 66
- implemented definitions with executable handlers: 66
- partial: 0
- defined_only: 0
- not_available: 0

`implemented` means the repository has a deterministic formula, typed input contract, missing-data behavior, lineage fields, and regression tests. A company can still return `value: null` when its local facts or prices are insufficient; that is an observation-level missing state, not a definition-level implementation gap.

The three counts are intentionally separate. The registry count is the number of `MetricDefinition` records. The executable handler count is the number of definitions covered by a professional engine handler, a legacy deterministic formula, or a price analytics handler. The API exposed count is the number of `MetricResult` rows returned by `/v1/companies/{symbol}/metrics`; tests require exactly one API row per registered definition and no duplicate codes.

## Implemented Metrics

### Legacy Financial Matrix Metrics

These remain available for existing company summary, screener, research flows, and as fallback handlers in `MetricCalculationService`. They use the compatible financial matrix path and return null with `missing_reason` on missing inputs or zero denominators. When a professional handler and a legacy formula share a code, the professional result wins in the API.

| Metric | Formula | Inputs | Period Rule | Missing Behavior | Tests |
| --- | --- | --- | --- | --- | --- |
| revenue | reported revenue | revenue | latest period | missing_input | `backend/tests/test_metric_registry.py` |
| revenue_yoy | revenue / comparable prior revenue - 1 | revenue | professional engine uses comparable period; legacy path uses adjacent row for compatibility | missing/zero denominator -> null | `backend/tests/test_metric_registry.py`, `backend/tests/test_professional_metrics.py` |
| revenue_cagr_3y | `(latest / oldest) ** (1 / years) - 1` | revenue | available history up to 3 years | insufficient_history | `backend/tests/test_metric_registry.py` |
| gross_profit | reported gross profit | gross_profit | latest period | missing_input | `backend/tests/test_metric_registry.py` |
| operating_profit | reported operating profit | operating_profit | latest period | missing_input | `backend/tests/test_metric_registry.py` |
| net_profit | net_profit or net_profit_parent | net_profit, net_profit_parent | latest period | missing_input | `backend/tests/test_metric_registry.py` |
| net_profit_yoy | net profit / comparable prior net profit - 1 | net_profit, net_profit_parent | professional engine uses comparable period | missing/zero denominator -> null | `backend/tests/test_professional_metrics.py` |
| gross_margin | gross_profit / revenue | gross_profit, revenue | latest period | missing/zero denominator -> null | `backend/tests/test_metric_registry.py` |
| operating_margin | operating_profit / revenue | operating_profit, revenue | latest period | missing/zero denominator -> null | `backend/tests/test_metric_registry.py` |
| net_margin | net_profit / revenue | net_profit, revenue | latest period | missing/zero denominator -> null | `backend/tests/test_metric_registry.py` |
| fcf | operating_cash_flow - standardized capital_expenditure outflow | operating_cash_flow, capital_expenditure | latest period | missing_input | `backend/tests/test_metric_registry.py` |
| roe | net_profit / average equity | net_profit, total_equity | latest plus previous period | zero denominator -> null | `backend/tests/test_metric_registry.py` |
| roa | net_profit / average assets | net_profit, total_assets | latest plus previous period | zero denominator -> null | `backend/tests/test_metric_registry.py` |
| roic_proxy | operating profit tax-adjusted / simple invested capital | operating_profit, tax, assets, cash, liabilities | latest period | proxy only; separate from true `roic` | `backend/tests/test_metric_registry.py` |
| dso, dio, dpo, cash_conversion_cycle | average balances over revenue/COGS days | receivables, inventory, payables, revenue, COGS | latest plus previous period | any missing component -> null | `backend/tests/test_metric_registry.py` |
| liquidity/leverage/per-share/valuation latest metrics | deterministic ratios from structured facts | balance sheet, income, shares, market_cap | latest period | missing/zero/non-positive earnings rules | `backend/tests/test_metric_registry.py` |

### Professional Financial Metrics

| Metric | Formula | Inputs | Period Rule | Source Lineage | Missing / Not Applicable Behavior | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| revenue_ttm | sum revenue from four contiguous comparable quarters | revenue | normalized single-quarter TTM | four quarter fact IDs and source URLs | insufficient_contiguous_quarters | `backend/tests/test_period_normalization.py`, `backend/tests/test_professional_metrics.py` |
| net_profit_ttm | sum net_profit_parent from four contiguous comparable quarters | net_profit_parent, net_profit fallback | normalized single-quarter TTM | four quarter fact IDs and source URLs | insufficient_contiguous_quarters | `backend/tests/test_professional_metrics.py` |
| fcf_ttm | TTM operating cash flow - standardized TTM capex outflow | operating_cash_flow, capital_expenditure | same four-quarter common window | OCF and capex fact IDs; selected_quarters | insufficient_common_ttm_window or misaligned_ttm_components | `backend/tests/test_professional_metrics.py` |
| fcf_yield | FCF TTM / equity market capitalization | FCF TTM, market_cap or close * shares | as_of latest eligible price | financial fact IDs plus price IDs | missing_market_cap, zero_denominator | `backend/tests/test_professional_metrics.py` |
| ebitda_ttm | direct EBITDA TTM or EBIT TTM + depreciation TTM + amortization TTM | ebitda or ebit/depreciation/amortization | direct EBITDA common window, or same four-quarter component common window | component fact IDs; selected_quarters | insufficient_common_ttm_window or misaligned_ttm_components | `backend/tests/test_professional_metrics.py` |
| net_debt | interest-bearing debt - cash and equivalents | interest_bearing_debt, cash_and_equivalents | latest financial period | debt/cash fact IDs | missing_debt_or_cash | `backend/tests/test_professional_metrics.py` |
| net_debt_to_ebitda | net_debt / EBITDA TTM | net_debt, EBITDA TTM | latest debt, TTM EBITDA | combined lineage | not_applicable_non_positive_ebitda | `backend/tests/test_professional_metrics.py` |
| enterprise_value | market cap + debt + preferred equity + NCI - cash | market cap, debt, optional preferred/NCI, cash | latest financial period and as_of price | fact IDs and price IDs | optional fields warn and mark basic_ev | `backend/tests/test_professional_metrics.py` |
| ev_to_ebitda | enterprise value / EBITDA TTM | EV, EBITDA TTM | latest EV, TTM EBITDA | combined lineage | not_applicable_industry, non-positive EBITDA | `backend/tests/test_professional_metrics.py` |
| pe_ttm | market cap / net_profit_parent TTM | market cap, net profit TTM | latest as_of market cap and inherited net profit TTM window | fact IDs and price IDs; selected_quarters | not_applicable_negative_earnings | `backend/tests/test_professional_metrics.py` |
| roic | EBIT TTM * (1 - normalized tax rate) / average invested capital | EBIT, tax/PBT, debt, equity, NCI, excess_cash | common EBIT/tax/PBT TTM window where available, begin/end average capital | fact IDs for numerator and capital periods; selected_quarters | not_applicable_industry, missing_average_invested_capital; misaligned tax components warn and use normalized assumption | `backend/tests/test_professional_metrics.py` |

### Price Analytics

All price analytics use a canonical adjusted-close return series with one symbol, one configured `adjustment_type`, one selected `data_source`, unique increasing trade dates, positive closes, a sample window, observation count, selected source reason, and assumptions.

| Metric | Formula | Inputs | Period Rule | Missing Behavior | Tests |
| --- | --- | --- | --- | --- | --- |
| return_1d, return_5d, return_20d, return_60d | close_t / close_t-n - 1 | adjusted close | n trading observations | insufficient_price_history | `backend/tests/test_price_analytics.py` |
| return_ytd | latest close / first close of year - 1 | adjusted close | calendar year to latest | insufficient_price_history | `backend/tests/test_price_analytics.py` |
| annualized_volatility | sample stdev(daily returns) * sqrt(252) | daily returns | configured sample window | insufficient_price_history | `backend/tests/test_price_analytics.py` |
| downside_volatility | sample stdev(negative daily returns) * sqrt(252) | negative daily returns | configured sample window | insufficient_price_history | `backend/tests/test_price_analytics.py` |
| maximum_drawdown | min(value_t / running_max_t - 1) | adjusted close | ordered price series | insufficient_price_history | `backend/tests/test_price_analytics.py` |
| beta | covariance(stock return, benchmark return) / variance(benchmark return) | aligned stock and benchmark returns | inner join by trade date | insufficient_price_history, zero_benchmark_variance | `backend/tests/test_price_analytics.py` |
| alpha | Jensen alpha annualized | aligned returns, risk-free rate, beta | aligned sample period | propagates beta missing reason | `backend/tests/test_price_analytics.py` |
| r_squared | correlation(stock, benchmark)^2 | aligned returns | aligned sample period | zero_variance | `backend/tests/test_price_analytics.py` |
| tracking_error | stdev(stock return - benchmark return) * sqrt(252) | aligned returns | aligned sample period | insufficient_price_history | `backend/tests/test_price_analytics.py` |
| information_ratio | annualized active return / tracking error | aligned returns | aligned sample period | zero_tracking_error | `backend/tests/test_price_analytics.py` |
| sharpe_ratio | (annualized return - risk_free_rate) / annualized volatility | daily returns | sample period | zero_volatility or insufficient history | `backend/tests/test_price_analytics.py` |
| sortino_ratio | (annualized return - risk_free_rate) / downside volatility | daily returns | sample period | zero_downside_volatility or insufficient history | `backend/tests/test_price_analytics.py` |

## Currency And as_of Rules

- Financial period normalization rejects mixed currencies with `currency_mismatch`.
- `FinancialFactRepository.periods(..., strict_as_of=True)` excludes facts with missing `publication_date` or publication dates later than `as_of_date`.
- Market cap uses direct trusted `market_cap` facts when available; otherwise it uses the latest price at or before `as_of_date` multiplied by shares outstanding.
- Missing values remain null with explicit reasons. No production path fabricates facts, prices, or benchmark returns.
