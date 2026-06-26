# Price Analytics

Updated: 2026-06-26

## Contract

`PriceAnalyticsService` receives typed `PricePoint` rows:

- id
- symbol
- trade_date
- close
- adjustment_type
- data_source

`MetricCalculationService` selects a canonical series before calling `PriceAnalyticsService`. The same selected series is also used by professional valuation metrics that need a latest price. The service does not forward-fill long missing price gaps and does not fabricate benchmark data.

## Canonical Series Policy

- One calculation uses one requested `symbol`; mixed symbols return `ambiguous_price_series`.
- China stock adjustment type is read from `CN_STOCK_ADJUSTMENT_TYPE`, default `qfq`.
- Source priority is read from `PRICE_SOURCE_PRIORITY`, default `local_prices,akshare,exchange,fixture_price,test`.
- If the configured adjustment type exists, other adjustment types are ignored rather than mixed.
- If multiple sources exist for the configured adjustment type, one source is selected by priority.
- Within the selected source, each `trade_date` must appear once, dates are sorted ascending, and `close` must be positive.
- If no unique valid series can be selected, price metrics return `quality_status: missing` with `missing_reason: ambiguous_price_series` or a more specific missing reason.

## Metrics

- 1D, 5D, 20D, 60D return: `adjusted_close_t / adjusted_close_t-n - 1`
- YTD return: latest adjusted close divided by first adjusted close in the latest calendar year minus 1
- annualized volatility: sample standard deviation of daily returns times `sqrt(trading_days_per_year)`
- downside volatility: sample standard deviation of negative daily returns times `sqrt(trading_days_per_year)`
- maximum drawdown: minimum `value_t / running_max_t - 1`, with drawdown start, trough, recovery date, and duration
- beta: covariance of stock and benchmark returns divided by benchmark return variance
- Jensen alpha: annualized stock return minus risk-free-adjusted beta expectation
- R squared: squared correlation of aligned stock and benchmark returns
- tracking error: sample standard deviation of active returns times `sqrt(trading_days_per_year)`
- information ratio: annualized active return divided by tracking error
- Sharpe ratio: annualized excess return divided by annualized volatility
- Sortino ratio: annualized excess return divided by downside volatility

## Alignment And Missing Behavior

- Stock and benchmark returns are inner-joined by trade date.
- Metrics require a configured minimum observation count.
- Insufficient history returns `missing_reason: insufficient_price_history`.
- Zero benchmark variance returns `missing_reason: zero_benchmark_variance`.
- Missing beta causes alpha to return the same missing reason.

## Lineage

Each price result records:

- `source_price_ids`
- `price_source`
- `start_date`
- `end_date`
- `observations_count`
- `adjustment_type`
- `data_source` through the API alias of `price_source`
- `selected_source_reason`
- `assumptions`
- `formula_version`
- `quality_status`

Benchmark metrics also record `benchmark_code` and `benchmark_source`.

## Tests

Coverage lives in `backend/tests/test_price_analytics.py` and includes normal returns, maximum drawdown, beta, alpha, zero benchmark variance, insufficient samples, volatility, lineage fields, mixed qfq/hfq/none inputs, multiple sources on the same date, duplicate selected-source dates, zero prices, negative prices, normal qfq selection, and API use of the selected adjustment/source policy.
