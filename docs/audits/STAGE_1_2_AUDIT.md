# Stage 1/2 Anti-Shortcut Audit

Updated: 2026-06-26

## Status Legend

PASS means directly verified. FAIL means verified broken. BLOCKED means a required external capability was unavailable. PARTIAL means real coverage exists but is incomplete. NOT_CONFIGURED means no configured capability exists. UNVERIFIED means not actually checked.

## Audit Results

- Stage 1: PASS locally.
- Stage 2: PASS locally.
- Python type check: PASS; mypy over `backend/src/finresearch`, 74 files, 0 errors. `python -m compileall` was not used as a type check.
- GitHub Actions: UNVERIFIED for the new commits until pushed and queried. YAML parsing is not counted as CI success.
- Alembic: PASS. `0001_initial_schema.py` now uses explicit Alembic operations. `0002_stage2_metadata_fields.py` adds Stage 2 metadata fields and supports downgrade.
- Security: PARTIAL. tracked-secret-file-check is only grep over tracked files. detect-secrets is the actual secret scan and passed locally.
- Python dependency audit: PASS for project-declared dependencies.
- npm dependency audit: PARTIAL due 2 moderate Next/PostCSS findings with only a breaking force fix available.

## Metric Formula Audit

| Metric | Formula / current behavior | Inputs | Period rule | Avg balance | Missing / zero / negative / currency / as_of behavior | Test | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ROE | `net_profit or net_profit_parent / average(total_equity or equity_parent)` | net profit, equity | latest plus previous row | yes | missing and zero denominator return null; negative profit allowed; currency mismatch returns null for all metrics; as_of latest period | `backend/tests/test_metric_registry.py` | implemented |
| ROA | `net_profit or net_profit_parent / average(total_assets)` | net profit, assets | latest plus previous row | yes | same as ROE | `backend/tests/test_metric_registry.py` | implemented |
| ROIC | true ROIC is not implemented; only `roic_proxy = operating_profit * (1 - tax_rate) / (total_assets - cash - current_liabilities)` | operating profit, tax, assets, cash, current liabilities | latest row | no | proxy only; do not label as exact ROIC | registry only | defined_only |
| Revenue TTM | no registered calculation | four comparable quarters required | not implemented | n/a | not available | none | not_available |
| Revenue YoY | `latest revenue / previous revenue - 1` | revenue | adjacent sorted rows; comparability not enforced | n/a | missing/zero previous returns null; cumulative-quarter normalization not implemented | `backend/tests/test_metric_registry.py` | partial |
| FCF | `operating_cash_flow - abs(capital_expenditure)` | OCF, capex | latest row | n/a | missing returns null; negative FCF allowed; currency mismatch guarded | `backend/tests/test_metric_registry.py` | implemented |
| FCF Yield | no registered calculation | FCF, market cap | not implemented | n/a | not available | none | not_available |
| DSO | `average(accounts_receivable) / revenue * 365` | receivables, revenue | latest plus previous row | yes | missing/zero revenue returns null | `backend/tests/test_metric_registry.py` | implemented |
| DIO | `average(inventory) / cost_of_goods_sold * 365` | inventory, COGS | latest plus previous row | yes | missing/zero COGS returns null | `backend/tests/test_metric_registry.py` | implemented |
| DPO | `average(accounts_payable) / cost_of_goods_sold * 365` | payables, COGS | latest plus previous row | yes | missing/zero COGS returns null | `backend/tests/test_metric_registry.py` | implemented |
| Cash Conversion Cycle | DSO + DIO - DPO | receivables, inventory, payables, revenue, COGS | latest plus previous row | yes | any component missing returns null | `backend/tests/test_metric_registry.py` | implemented |
| Net Debt | `interest_bearing_debt or total_debt - cash or cash_and_equivalents` | debt, cash | latest row | no | missing returns null; negative net debt allowed | registry tests cover missing; formula audited | implemented |
| Net Debt / EBITDA | no registered calculation | net debt, EBITDA | not implemented | n/a | not available | none | not_available |
| Interest Coverage | `operating_profit / interest_expense` | operating profit, interest expense | latest row | no | missing/zero denominator returns null; negative operating profit allowed | registry tests cover denominator behavior | implemented |
| PE TTM | no TTM calculation; current `pe` only uses latest net profit and now rejects non-positive earnings | market cap, net profit | latest row only | no | negative/zero earnings returns `not_applicable_negative_earnings` | `backend/tests/test_metric_registry.py` | not_available |
| EV / EBITDA | no registered calculation | EV, EBITDA | not implemented | n/a | not available | none | not_available |
| Beta | no calculation; benchmark-aligned returns not implemented | security returns, benchmark returns | aligned return series required | n/a | not available | none | not_available |
| Alpha | no calculation; benchmark-aligned returns not implemented | security returns, benchmark returns, risk-free assumption | aligned return series required | n/a | not available | none | not_available |
| Annualized Volatility | no calculation | return series | trading-day convention required | n/a | not available | none | not_available |
| Maximum Drawdown | no calculation | price or equity curve series | ordered time series required | n/a | not available | none | not_available |

## Security Notes

- subprocess usage is limited to `subprocess.run(argv, shell=False)` in the Agent Reach adapter with timeouts.
- Cookie/token logging: no frontend connector status test payload exposes cookie/token/password fields; detect-secrets found 0 findings.
- Config interface locality: FastAPI CORS is restricted to `localhost:3000` and `127.0.0.1:3000`; dev servers bind to loopback in smoke tests.
- URL/SSRF: direct web reads arbitrary HTTP(S) URLs through `requests.get`; this remains PARTIAL hardening and should be constrained before non-local deployment.

## Frontend Coverage Added

- Market API failure.
- `no_snapshot` empty state.
- Single market card failure isolation.
- K-line no-data state.
- Screener empty results.
- Screener invalid sort.
- Screener pagination.
- Background research failed status.
- Ollama unavailable status.
- Connector disabled status.
