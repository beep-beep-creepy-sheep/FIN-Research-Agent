# Project State

Updated: 2026-06-29

## Snapshot

- Stage 1 status: PASS.
- Stage 2 status: PASS locally for final metric integrity, canonical price series, and common TTM windows.
- Stage 3 status: PASS. Stage 3 is merged into `main`; GitHub Actions run `28295527902` for `8b08189f8a0ee1d7aaaa12870231ccbceab86dec` completed success for backend, frontend, and e2e on 2026-06-28.
- Stage 4 status: PASS. Stage 4 is merged into `main`; GitHub Actions run `28318788762` for `5a4c42916308e8d18e74c62f3820fd45c20e86f4` completed success for backend, frontend, and e2e on 2026-06-28.
- Stage 5 status: PASS. Stage 5 is merged into `main`; GitHub Actions run `28326223624` for `b2612924a105feec0ddcf1b0a4c467ba7777bfdc` completed success for backend, frontend, and e2e on 2026-06-28.
- Stage 6 status: PASS. Stage 6 is merged into `main`; PR #7 `feat: implement stage 6 institutional reporting`; GitHub Actions run `28328935273` for `37af5282a0686c0286fa720c8bb64976c637356c` completed success for backend, frontend, and e2e on 2026-06-28.
- Stage 7 status: PASS. Stage 7 is merged into `main`; PR #8 `feat: implement stage 7 portfolio risk alerts calendar`; GitHub Actions run `28330396205` for merge commit `6b8799840f40730efb9756355d73f4411e87351e` completed success for backend, frontend, and e2e on 2026-06-28.

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

## Stage 6 AI Orchestration / Institutional Report State

- Research evidence bundle: implemented. It combines local company metadata, financial facts, prices, professional analysis, peer sets, peer metrics, valuation runs, filings, documents, data-quality issues, prompt-injection flags, and evidence IDs with deterministic bundle hashes.
- Deterministic report builder: implemented with sections for metadata, executive summary, company profile, financial analysis, industry-pack analysis, peer comparison, valuation lab, risk/data quality, evidence appendix, methodology, and disclaimers.
- AI orchestration boundary: implemented for optional local Ollama-compatible narration. LLM usage defaults off and deterministic fallback is used when disabled, unavailable, blocked by prompt-injection risk, or rejected by validation.
- Report validation: implemented with evidence ID checks, local path leak checks, prompt-injection warnings, and forbidden wording rejection before persistence.
- Persistence: report runs, sections, and prompt audit records are modeled and covered by Alembic revision `0006_stage6_reports`.
- API: `/v1/companies/{symbol}/report`, `/report/latest`, `/report/runs`, `/v1/report-runs/{run_id}`, `/markdown`, `/html`, `/validation`, `/evidence`, and `/regenerate-section`.
- Frontend: company page includes an Institutional Report panel with deterministic/AI toggle, strict-as-of toggle, language selector, section selector, validation status, evidence coverage, report preview, Markdown export, HTML print view, and warning states.
- Guardrails: no broker login, no automatic trading, no promised returns, no target price output, no model-created financial facts, and no model-created citations.
- Verification status: Stage 6 local quality gates passed on 2026-06-28; GitHub Actions run `28328935273` completed success for backend, frontend, and e2e on 2026-06-28.

## Stage 6 Local Gates Run

- Python tests: PASS, `PYTHONPATH=.:backend/src pytest -q`, 140 passed.
- Focused Stage 6 tests: PASS, `PYTHONPATH=.:backend/src pytest -q backend/tests/test_stage6_reports.py`, 5 passed.
- Ruff: PASS, `ruff check .`.
- Python type check: PASS, `PYTHONPATH=.:backend/src python -m mypy backend/src/finresearch`, 98 files, 0 errors.
- Frontend tests: PASS, `cd frontend && npm test`, 15 passed.
- Frontend TypeScript: PASS, `cd frontend && npx tsc --noEmit`.
- Frontend build: PASS, `cd frontend && npm run build`.
- Playwright Chromium: PASS, `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 ... npm run test:e2e -- --project=chromium`, 5 passed.
- SQLite Alembic empty upgrade and repeated upgrade: PASS through `0006_stage6_reports`.
- PostgreSQL migration verification: BLOCKED_LOCAL_TOOLING, `pg_isready` and `psql` are not installed in this local environment.
- FastAPI/report API smoke: PASS, health endpoint, report generation, and Markdown export validated through `TestClient`.
- Worker smoke: PASS, `run_once()` returns cleanly with no queued jobs.
- Secret scan: PASS, `make secret-scan`, detect-secrets findings 0.
- Python dependency audit: PASS, `make python-audit`, no known vulnerabilities.
- npm dependency audit high-severity gate: PASS, `npm audit --audit-level=high`; 2 moderate Next/PostCSS findings remain.

## Stage 7 Portfolio / Risk / Alerts / Calendar State

- Portfolio model: implemented for local research portfolios, manual positions, watch items, snapshots, risk runs, alert rules/events, and calendar events through Alembic revision `0007_stage7_portfolio`.
- Portfolio analytics: implemented for market value when prices exist, cost value when cost basis exists, unrealized gain/loss when both exist, manual weight override, equal-weight watch portfolios, exposure buckets, concentration, top positions, and missing-data summaries.
- Portfolio risk: implemented for weighted volatility, missing benchmark beta state, drawdown proxy, concentration, data-quality risk, stale price risk, missing filing risk, valuation risk flags, report validation flags, optional correlation matrix, and diversification score.
- Portfolio performance: implemented for local daily value series, cumulative return, period return, volatility, max drawdown, contribution, benchmark missing state, and partial coverage warnings.
- Alerts: implemented for local rule storage, manual evaluation, alert events, acknowledge/dismiss states, and missing-data skipped states.
- Calendar: implemented for local manual events and filtered event queries; future official dates are not guessed.
- Portfolio report: implemented as deterministic Stage 7 sections with Stage 6 validation guard naming and missing-data limitations.
- API/frontend: `/v1/portfolios`, `/v1/calendar/events`, portfolio detail analytics, alerts, calendar, and report endpoints; frontend pages at `/portfolios`, `/portfolios/[portfolioId]`, and `/calendar`.
- Guardrails: no broker login, no account sync, no automatic trading, no real order placement, no external push service, no target price output, and no rebalancing instruction output.
- Verification status: Stage 7 local quality gates passed on 2026-06-28; GitHub Actions run `28330396205` for merge commit `6b8799840f40730efb9756355d73f4411e87351e` completed success for backend, frontend, and e2e on 2026-06-28.

## Stage 7 Local Gates Run

- Python tests: PASS, `PYTHONPATH=.:backend/src pytest -q`, 145 passed.
- Focused Stage 7 tests: PASS, `PYTHONPATH=.:backend/src pytest -q backend/tests/test_stage7_portfolio_risk_alerts.py`, 5 passed.
- Stage 3-7 regression tests: PASS, focused Stage 3, Stage 4, Stage 5, Stage 6, and Stage 7 suites, 37 passed.
- Ruff: PASS, `ruff check .`.
- Python type check: PASS, `PYTHONPATH=.:backend/src python -m mypy backend/src/finresearch`, 101 files, 0 errors.
- Frontend tests: PASS, `cd frontend && npm test`, 16 passed.
- Frontend TypeScript: PASS, `cd frontend && npx tsc --noEmit`.
- Frontend build: PASS, `cd frontend && npm run build`.
- Playwright Chromium: PASS, `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 ... npm run test:e2e -- --project=chromium`, 7 passed.
- SQLite Alembic empty upgrade: PASS through `0007_stage7_portfolio`.
- PostgreSQL migration verification: BLOCKED_LOCAL_TOOLING, `pg_isready` is not installed in this local environment.
- FastAPI smoke: PASS, `/health` returned ok against a local FastAPI server.
- Worker smoke: PASS, `run_once()` processed a queued fixture sync job successfully against the local smoke database.
- Portfolio API smoke: PASS, local portfolio create/detail/summary/risk/performance endpoints returned successfully.
- Alerts evaluate smoke: PASS, local alert rule evaluation created a deterministic alert event.
- Calendar API smoke: PASS, local manual event create/list returned successfully.
- Secret scan: PASS, `make tracked-secret-file-check` and `make secret-scan`; detect-secrets findings 0.
- Python dependency audit: PASS, `make python-audit`, no known vulnerabilities.
- npm dependency audit high-severity gate: PASS, `npm audit --audit-level=high`; 2 moderate Next/PostCSS findings remain.

## Known Limitations

- Current API price analytics route does not yet infer benchmark series automatically; benchmark metrics return missing unless a caller supplies aligned benchmark inputs to the service.
- Currency enforcement is strict for financial period normalization; market-cap currency conversion is not attempted.
- npm audit high-severity gate passes; moderate findings remain in Next's transitive PostCSS dependency unless upstream provides a non-breaking fix.
- Local Ollama report narration remains optional and off by default; deterministic reports remain the default behavior.
- Portfolio currency conversion is not attempted; currency mismatches are surfaced as missing/limitation states.
- Alert evaluation is local/manual and does not send external notifications.
- SSE, SZSE, BSE, and SEC EDGAR live adapters remain future work; their fixture/definition coverage is not live coverage.
- Live source smoke remains opt-in and must be reported separately from fixture verification.
- Portfolios are local research portfolios only, not broker accounts.
- Automatic trading, order placement, and automatic rebalancing remain out of scope.
