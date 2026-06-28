# Portfolio Risk Analytics

Risk analytics are deterministic research indicators.

## Metrics

- Weighted volatility when local price history is sufficient.
- Benchmark beta returns `insufficient_data` when aligned benchmark series is missing.
- Maximum drawdown proxy from local price history.
- Single-name, sector, industry, and currency concentration.
- Data-quality, stale-price, missing-filing, valuation, and report-validation flags.
- Correlation matrix only when enough local price observations exist.

Missing data never defaults to healthy. Each warning is tied to a symbol, metric, or source where possible.
