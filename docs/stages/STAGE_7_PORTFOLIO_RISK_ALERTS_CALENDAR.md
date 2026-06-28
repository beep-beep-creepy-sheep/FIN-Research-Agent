# Stage 7: Portfolio / Risk / Alerts / Calendar

Stage 7 upgrades the local research terminal from single-company research to a local portfolio research workspace.

## Implemented

- Manual portfolio, position, and watch-item models.
- Deterministic exposure, risk, performance, and data-quality analytics.
- Local alert rules and alert events with manual evaluation.
- Local calendar events with date range, portfolio, symbol, and severity filters.
- Deterministic portfolio report that reuses the Stage 6 validation boundary.
- FastAPI endpoints for portfolios, positions, watch items, risk, performance, alerts, calendar, and portfolio reports.
- Frontend pages at `/portfolios`, `/portfolios/[portfolioId]`, and `/calendar`.

## Not Implemented

Stage 7 does not add broker login, trading account connections, real order placement, paper order simulation, automatic rebalancing, tax reporting, multi-user auth, external push services, paid APIs, or real-time streaming.

## Guardrails

Portfolio output is for local public-information research. Alerts are reminders, not trading instructions. Calendar entries are only shown when already stored locally; future filing dates are not guessed.

## Stage 8 Handoff

Stage 8 may build on persisted portfolios, alert state, calendar events, and portfolio reports for production/security/performance/release work. Stage 7 intentionally leaves deployment and hardening out of scope.
