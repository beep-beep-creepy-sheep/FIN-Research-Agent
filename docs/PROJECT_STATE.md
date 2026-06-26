# Project State

Updated: 2026-06-26

## Snapshot

- Stage 1 status: PASS locally from the prior anti-shortcut audit; this turn did not start Stage 3.
- Stage 2 status: PASS locally for professional metric completion.
- Current branch: main.
- Current commit at this document update: pending local Stage 2 professional metric commits on top of `8a9b92dd64fdc8c386bd67cd938824e3e4a39295`.
- origin/main at update start: `8a9b92dd64fdc8c386bd67cd938824e3e4a39295`.
- GitHub Actions true status: UNVERIFIED until these commits are pushed and backend, frontend, and e2e jobs complete.

## Local Gates Run During Stage 2 Completion

- Python tests: PASS, `PYTHONPATH=backend/src pytest -q backend/tests`, 60 passed.
- Ruff: PASS, `PYTHONPATH=backend/src ruff check .`.
- Real Python type check: PASS, `PYTHONPATH=backend/src mypy backend/src/finresearch`, 78 files, 0 errors.
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
- npm dependency audit: PARTIAL, `npm audit --audit-level=moderate`, 2 moderate Next/PostCSS findings; available fix is `npm audit fix --force` and would install a breaking Next version, so no force upgrade was applied.

## Stage 2 Metric State

- Implemented metric definitions: 66.
- Partial metric definitions: 0.
- Defined-only metric definitions: 0.
- Not-available metric definitions: 0.
- Professional financial engine: implemented for Revenue TTM, Net Profit TTM, FCF TTM, FCF Yield, EBITDA TTM, Net Debt, Net Debt/EBITDA, Enterprise Value, EV/EBITDA, PE TTM, and true ROIC.
- Price analytics engine: implemented for 1D/5D/20D/60D/YTD returns, annualized volatility, downside volatility, maximum drawdown, beta, alpha, R squared, tracking error, information ratio, Sharpe, and Sortino.
- Metric API: `/v1/financials/{symbol}/metrics` now returns calculation state, implementation status, formula, inputs, lineage IDs, warnings, missing reason, and calculation version.
- Frontend state handling: frontend tests distinguish not implemented, not applicable, implemented-but-missing-data, calculated with warnings, and calculated metric states.

## Data And Lineage

- `FinancialPeriod` preserves reporting dates, publication date, statement scope, currency, quality, version, fact IDs, source URLs, source pages, and values.
- `CalculationContext` carries financial periods, price series, benchmark series, as_of settings, currency, trading-day assumption, risk-free rate, industry, and calculation version.
- `MetricObservation` schema now includes implementation metadata and price/benchmark/assumption fields through Alembic revision `0003_professional_metric_metadata`.
- Missing local facts or prices return null observations with explicit `missing_reason`; the code does not fabricate financial or market data.

## Known Limitations

- GitHub Actions status is UNVERIFIED until the pushed commit is checked.
- Current API price analytics route does not yet infer benchmark series automatically; benchmark metrics return missing unless a caller supplies aligned benchmark inputs to the service.
- Currency enforcement is strict for financial period normalization; market-cap currency conversion is not attempted.
- npm audit moderate findings remain in Next's transitive PostCSS dependency unless upstream provides a non-breaking fix.

## Next Step

- Finish full local gate, commit, push, query GitHub Actions, and stop before Stage 3.
