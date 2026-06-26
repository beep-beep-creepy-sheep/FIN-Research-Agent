# Stage 1/2 Audit

Updated: 2026-06-26

## Status Legend

PASS means directly verified. FAIL means verified broken. BLOCKED means a required external capability was unavailable. PARTIAL means real coverage exists but is incomplete. NOT_CONFIGURED means no configured capability exists. UNVERIFIED means not actually checked.

## Current Status

- Stage 1: PASS locally from prior anti-shortcut gate.
- Stage 2 professional metric completion: PASS locally pending pushed GitHub Actions.
- Full Python tests: PASS; `PYTHONPATH=.:backend/src pytest -q`, 85 passed, covering root `tests/` and `backend/tests/`.
- Python type check: PASS; `PYTHONPATH=.:backend/src python -m mypy backend/src/finresearch`, 78 files, 0 errors. `python -m compileall` is not counted as a type check.
- Final commit SHA: see Git HEAD and final checkpoint output after this document commit.
- GitHub Actions: UNVERIFIED until the final commit is pushed and queried.
- Alembic: PASS locally. Revision `0003_professional_metric_metadata.py` uses explicit column operations and downgrade; SQLite empty, current PostgreSQL, and temporary empty PostgreSQL upgrades all passed.
- Security: PARTIAL overall because npm audit has unresolved moderate advisories. tracked-secret-file-check is PASS but remains only a grep-style check and is not a complete security scan; detect-secrets is PASS with 0 findings.
- Python dependency audit: PASS, no known vulnerabilities.
- npm dependency audit: PARTIAL, 2 moderate Next/PostCSS findings; available `npm audit fix --force` would make a breaking Next change, so it was not applied.

## Metric Status Counts

- implemented: 66
- partial: 0
- defined_only: 0
- not_available: 0

## Professional Metric Audit

| Metric | Formula / Behavior | Inputs | Period Rule | Avg Balance | Missing / Zero / Negative / Currency / as_of Behavior | Tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROE | net profit / average equity | net_profit or net_profit_parent, equity | latest plus previous compatible row | yes | missing/zero returns null; mixed currency rejected in matrix path | `backend/tests/test_metric_registry.py` | PASS |
| ROA | net profit / average assets | net_profit or net_profit_parent, assets | latest plus previous compatible row | yes | missing/zero returns null; mixed currency rejected | `backend/tests/test_metric_registry.py` | PASS |
| ROIC | EBIT TTM * (1 - normalized tax rate) / average invested capital | EBIT, tax/PBT, debt, equity, optional NCI/excess cash | TTM numerator, begin/end capital | yes | banks/insurance/securities return not_applicable_industry; insufficient capital returns null | `backend/tests/test_professional_metrics.py` | PASS |
| Revenue TTM | sum revenue from four contiguous normalized quarters | revenue | four comparable quarters | n/a | missing quarter returns insufficient_contiguous_quarters; no fabricated data | `backend/tests/test_period_normalization.py`, `backend/tests/test_professional_metrics.py` | PASS |
| Revenue YoY | comparable period revenue / prior comparable revenue - 1 | revenue | annual-vs-annual or same quarter prior year | n/a | missing comparable period or zero denominator returns null | `backend/tests/test_period_normalization.py` | PASS |
| Net Profit TTM | sum parent net profit from four contiguous normalized quarters | net_profit_parent, net_profit fallback | four comparable quarters | n/a | insufficient_contiguous_quarters | `backend/tests/test_professional_metrics.py` | PASS |
| Net Profit YoY | comparable period net profit / prior comparable period - 1 | net_profit_parent, net_profit fallback | annual-vs-annual or same quarter prior year | n/a | missing comparable period or zero denominator returns null | `backend/tests/test_professional_metrics.py` | PASS |
| FCF TTM | TTM OCF - standardized TTM capex outflow | operating_cash_flow, capital_expenditure | four comparable quarters | n/a | missing input returns null; positive capex warns and is treated as outflow | `backend/tests/test_professional_metrics.py` | PASS |
| FCF Yield | FCF TTM / market capitalization | FCF TTM, market_cap or price * shares | as_of market cap | n/a | missing market cap or zero denominator returns null; source price ID retained | `backend/tests/test_professional_metrics.py` | PASS |
| EBITDA TTM | direct EBITDA TTM or EBIT TTM + depreciation TTM + amortization TTM | ebitda or ebit/depreciation/amortization | four comparable quarters | n/a | does not use operating_profit as EBITDA; missing components return null | `backend/tests/test_professional_metrics.py` | PASS |
| Net Debt | interest-bearing debt - cash equivalents | debt, cash | latest financial period | n/a | negative net debt allowed; missing debt/cash returns null | `backend/tests/test_professional_metrics.py` | PASS |
| Net Debt / EBITDA | net debt / EBITDA TTM | net debt, EBITDA TTM | latest debt, TTM EBITDA | n/a | EBITDA <= 0 returns not_applicable_non_positive_ebitda | `backend/tests/test_professional_metrics.py` | PASS |
| Enterprise Value | market cap + debt + preferred equity + NCI - cash | market cap, debt, optional preferred/NCI, cash | latest financial period plus as_of price | n/a | optional components assumed zero only with warnings/basic_ev quality | `backend/tests/test_professional_metrics.py` | PASS |
| EV / EBITDA | enterprise value / EBITDA TTM | EV, EBITDA TTM | latest EV, TTM EBITDA | n/a | industry not applicable and non-positive EBITDA handled | `backend/tests/test_professional_metrics.py` | PASS |
| PE TTM | market cap / net_profit_parent TTM | market cap, net profit TTM | latest market cap and TTM earnings | n/a | earnings <= 0 returns not_applicable_negative_earnings | `backend/tests/test_professional_metrics.py` | PASS |
| Annualized Volatility | sample stdev(daily returns) * sqrt(252) | adjusted close | ordered price series | n/a | insufficient history returns null | `backend/tests/test_price_analytics.py` | PASS |
| Maximum Drawdown | min(value / running max - 1) | adjusted close | ordered price series | n/a | insufficient history returns null; start/trough/recovery metadata retained | `backend/tests/test_price_analytics.py` | PASS |
| Beta | cov(stock, benchmark) / var(benchmark) | aligned stock and benchmark returns | inner join by trade date | n/a | insufficient history or zero benchmark variance returns null | `backend/tests/test_price_analytics.py` | PASS |
| Alpha | Jensen annualized alpha | aligned returns, beta, risk-free rate | inner joined sample | n/a | propagates beta missing reason; assumptions recorded | `backend/tests/test_price_analytics.py` | PASS |

## Period Normalization Audit

- Cumulative quarter conversion: PASS.
- Cumulative YTD input recognition: PASS. Dates such as `YYYY-01-01` to `YYYY-06-30` or `YYYY-09-30` are treated as `cumulative_ytd`.
- Single-quarter input recognition: PASS. Dates such as `YYYY-04-01` to `YYYY-06-30`, `YYYY-07-01` to `YYYY-09-30`, and `YYYY-10-01` to `YYYY-12-31` are treated as `single_quarter` and are not differenced again.
- Mixed single-quarter and cumulative input: PASS. Single-quarter facts are used directly for their quarter; cumulative facts remain available for later cumulative differencing.
- Unknown flow basis: PASS. Ambiguous dates or explicitly unknown basis produce `ambiguous_flow_basis` and no guessed flow value.
- TTM contiguous-quarter enforcement: PASS.
- Annual comparable YoY: PASS.
- Currency mismatch handling: PASS.
- Restatement precedence: PASS.
- strict_as_of repository filtering: PASS, `backend/tests/test_repositories.py` covers both raw fact listing and typed `FinancialPeriod` output.
- Source lineage: PASS. Cumulative differencing preserves both current and prior fact IDs; single-quarter values preserve only their own fact ID.

## API And Frontend Audit

- `/v1/financials/{symbol}/metrics` returns implementation status, quality status, missing reason, formula, input values, source fact IDs, source price IDs, warnings, periods, price metadata, assumptions, and calculation version.
- Frontend metric state classifier distinguishes not implemented, not applicable, implemented but missing data, calculated with warnings, and calculated.
- Existing market page, screener, research, and worker compatibility tests remain part of the full gate.

## Known Limitations

- GitHub Actions status: UNVERIFIED until pushed and queried for backend, frontend, and e2e jobs.
- Benchmark series are implemented at service level but are not auto-discovered by the current company metrics API.
- Market cap currency conversion is not attempted; mismatched currencies return missing rather than converted values.
- npm audit remains PARTIAL for the documented moderate Next/PostCSS advisory.

## Stage 3 Handoff Notes

- Add automatic benchmark index selection and loading for the company metrics API.
- Select China A-share defaults from exchange, market, and industry configuration rather than hard-coding one index.
- Return `benchmark_code`, `benchmark_source`, and selection reason to the frontend.
- If benchmark data is unavailable, Beta and Alpha should return explicit benchmark missing reasons.
