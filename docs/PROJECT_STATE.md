# Project State

Updated: 2026-06-28

## Snapshot

- Stage 1 status: PASS.
- Stage 2 status: PASS locally for final metric integrity, canonical price series, and common TTM windows.
- Stage 3 status: PASS. Stage 3 is merged into `main`; GitHub Actions run `28295527902` for `8b08189f8a0ee1d7aaaa12870231ccbceab86dec` completed success for backend, frontend, and e2e on 2026-06-28.
- Stage 4 status: PASS. Stage 4 is merged into `main`; GitHub Actions run `28318788762` for `5a4c42916308e8d18e74c62f3820fd45c20e86f4` completed success for backend, frontend, and e2e on 2026-06-28.
- Stage 5 status: IN_PROGRESS on branch `feature/stage-5-peers-screener-valuation`.
- Current branch: feature/stage-5-peers-screener-valuation.
- Current Stage 5 base: `5a4c42916308e8d18e74c62f3820fd45c20e86f4`.
- origin/main at Stage 5 start: `5a4c42916308e8d18e74c62f3820fd45c20e86f4`.
- GitHub Actions true status for Stage 5: UNVERIFIED until this branch is pushed and backend, frontend, and e2e jobs complete.

## Local Gates Run During Stage 2 Completion

- Python tests: PASS, `PYTHONPATH=.:backend/src pytest -q`, 108 passed, covering root `tests/` and `backend/tests/`.
- Ruff: PASS, `ruff check .`.
- Real Python type check: PASS, `PYTHONPATH=.:backend/src python -m mypy backend/src/finresearch`, 79 files, 0 errors.
- Frontend tests: PASS, `npm test`, 12 passed.
- Frontend TypeScript: PASS, `npx tsc --noEmit`.
- Frontend build: PASS, `npm run build`.
- Playwright: PASS after starting FastAPI on `127.0.0.1:8000`, `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run test:e2e -- --project=chromium`, 4 passed.
- SQLite Alembic empty upgrade: PASS, empty SQLite database upgraded to head and repeated.
- PostgreSQL current database upgrade: PASS, existing PostgreSQL database upgraded to head and repeated.
- PostgreSQL empty database upgrade: PASS, random temporary PostgreSQL database upgraded to head and repeated, then dropped.
- tracked-secret-file-check: PASS; tracked file pattern grep only, not a complete secret scan.
- Secret scan: PASS, `make secret-scan`, detect-secrets findings 0.
- Python dependency audit: PASS, `make python-audit`, no known vulnerabilities.
- npm dependency audit: PASS for the required high-severity gate, `npm audit --audit-level=high`; 2 moderate Next/PostCSS findings remain, and the available fix is `npm audit fix --force` with a breaking Next version, so no force upgrade was applied.

## Stage 2 Metric State

- Registered metric definitions: 66.
- Executable metric handler coverage: 66 unique metric codes across professional, legacy deterministic, and price analytics handlers.
- API exposed metric results: 66, one result per registered definition, with duplicate codes disallowed by tests.
- Implemented metric definitions with executable handlers: 66.
- Partial metric definitions: 0.
- Defined-only metric definitions: 0.
- Not-available metric definitions: 0.
- Unified metric API: `/v1/companies/{symbol}/metrics` is orchestrated by `MetricCalculationService`; professional results take precedence over legacy deterministic formulas, legacy formulas fill uncovered financial metrics, and price metrics come from `PriceAnalyticsService`.
- Professional financial engine: implemented for Revenue TTM, Net Profit TTM, FCF TTM, FCF Yield, EBITDA TTM, Net Debt, Net Debt/EBITDA, Enterprise Value, EV/EBITDA, PE TTM, and true ROIC.
- Price analytics engine: implemented for 1D/5D/20D/60D/YTD returns, annualized volatility, downside volatility, maximum drawdown, beta, alpha, R squared, tracking error, information ratio, Sharpe, and Sortino.
- Metric API: `/v1/companies/{symbol}/metrics` now returns calculation state, implementation status, formula, inputs, lineage IDs, warnings, missing reason, calculation version, adjustment type, selected price source, selected source reason, and observation count.
- Frontend state handling: frontend tests distinguish not implemented, not applicable, implemented-but-missing-data, calculated with warnings, and calculated metric states.
- Period basis recognition: PASS. `PeriodNormalizationService` distinguishes `single_quarter`, `cumulative_ytd`, `annual`, and `unknown` flow inputs.
- Single-quarter inputs: PASS. Q2/Q3/Q4 single-quarter reports are preserved and are not differenced against prior quarters.
- Cumulative YTD inputs: PASS. Q2/Q3/Q4 cumulative reports are differenced only against prior cumulative reports.
- Mixed flow basis inputs: PASS. Single-quarter facts win for their own quarter while cumulative facts remain available for later cumulative differencing.
- Ambiguous flow basis inputs: PASS. Unknown or missing flow period basis returns `ambiguous_flow_basis` and does not guess.
- Source lineage: PASS. Differenced quarters retain both current and prior fact IDs; direct single-quarter values retain only their own fact IDs.
- Legacy financial metric lineage: PASS. `MetricCalculationService` no longer flattens `FinancialPeriod` inputs into a context-free matrix for API fallback metrics. Successful legacy financial metrics carry the actual participating `source_fact_ids`, `source_urls`, `input_values`, `period_start`, `period_end`, `as_of`, and formula version. IDs are selected from the fields used by each formula, not from all facts in the period; two-period and average-balance metrics retain both latest and prior balance fact IDs.
- Legacy period compatibility: PASS. Legacy fallback metrics require compatible currency, report type, statement scope, consolidation flag, flow basis, and period boundaries. Same-period flow ratios use one flow period; ROE/ROA and working-capital day metrics require a matching latest flow period plus compatible beginning and ending balance periods; point-in-time ratios use the same report period. Incompatible or unavailable periods return explicit `missing_reason` values instead of guessing.
- Canonical price series: PASS. Each calculation uses one symbol, one configured adjustment type, one selected data source, unique increasing trade dates, and positive closes. China stock adjustment type defaults to `CN_STOCK_ADJUSTMENT_TYPE=qfq`; source priority defaults to `PRICE_SOURCE_PRIORITY=local_prices,akshare,exchange`.
- Test price source isolation: PASS. `fixture_price` and `test` are disabled outside tests unless `PYTEST_CURRENT_TEST`, `APP_ENV=test`, or `ALLOW_TEST_DATA_SOURCES=true` is present. Non-test calculations skip those sources and return `test_price_sources_disabled` when no real source remains.
- Common TTM windows: PASS. FCF TTM, EBITDA TTM component fallback, ROIC tax components, PE TTM, and FCF Yield expose the selected four-quarter window and do not silently combine mismatched quarters.

## Data And Lineage

- `FinancialPeriod` preserves reporting dates, publication date, statement scope, currency, quality, version, fact IDs, source URLs, source pages, and values.
- `CalculationContext` carries financial periods, price series, benchmark series, as_of settings, currency, trading-day assumption, risk-free rate, industry, and calculation version.
- `MetricObservation` schema now includes implementation metadata and price/benchmark/assumption fields through Alembic revision `0003_professional_metric_metadata`.
- Missing local facts or prices return null observations with explicit `missing_reason`; the code does not fabricate financial or market data.

## Stage 4 Professional Analysis State

- Analysis data contract: implemented in `finresearch.services.analysis`.
- Industry packs: `general`, `bank`, and `consumer_manufacturing`.
- Scoring: transparent research-quality components with insufficient-data behavior.
- Evidence: findings retain metric fact IDs, price IDs, source URLs, evidence markers, and limitations.
- strict_as_of: analysis uses existing repository filtering before metric calculation.
- API: `/v1/companies/{symbol}/analysis`, `/analysis/findings`, `/analysis/report`, `/analysis/quality`, `/industry-pack`, and `/v1/analysis-runs`.
- Frontend: company page Professional Analysis panel with partial failure handling and insufficient-data state.
- Non-goals preserved: no target price, no trading signal, no broker login, no automatic order placement, no paid API dependency.

## Stage 5 Peers / Screener / Valuation State

- Peer set service: implemented. It uses local industry, exchange, listing-board signals and manual overrides; unknown industry returns `insufficient_peer_data`; banks are not mixed with manufacturing or consumer peers.
- Peer metrics matrix: implemented with rank, percentile, z-score, missing reasons, not-applicable states, and explicit outlier policy.
- Screener: enhanced with market, exchange, industry, board, growth, margin, ROE, ROIC, FCF yield, leverage, valuation filters, include-missing behavior, presets, and JSON/CSV export.
- Relative valuation: implemented for PE TTM, EV/EBITDA, FCF yield, PB, and PS where local data supports them.
- DCF / owner earnings scenario: implemented with bounded assumptions, base/bear/bull support, sensitivity tables, evidence, limitations, and per-share output only when shares outstanding is locally available.
- Persistence: peer sets, peer members, valuation runs, valuation assumptions, and screen presets are modeled and covered by Alembic revision `0005_stage5_peers`.
- Frontend: company page includes Peers, Peer Metrics Matrix, and Valuation Lab sections; screener includes expanded filters, missing-data status, presets, and export.
- Guardrails: no broker login, no automatic trading, no promised returns, no buy/sell/hold output, and no target price output.

## Known Limitations

- Stage 5 GitHub Actions status is UNVERIFIED until the branch is pushed and checked.
- Current API price analytics route does not yet infer benchmark series automatically; benchmark metrics return missing unless a caller supplies aligned benchmark inputs to the service.
- Currency enforcement is strict for financial period normalization; market-cap currency conversion is not attempted.
- npm audit high-severity gate passes; moderate findings remain in Next's transitive PostCSS dependency unless upstream provides a non-breaking fix.

## Stage 5 Todo

- Complete local quality gates and push Stage 5 branch.
- Observe GitHub Actions backend, frontend, and e2e.
- SSE, SZSE, BSE, and SEC EDGAR live adapters remain future work; their fixture/definition coverage is not live coverage.
- Live source smoke remains opt-in and must be reported separately from fixture verification.
