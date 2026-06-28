# Portfolio Model

Portfolios are local research containers, not brokerage accounts.

## Tables

- `portfolios`
- `portfolio_holdings`
- `portfolio_watch_items`
- `portfolio_snapshots`
- `portfolio_risk_runs`
- `portfolio_alert_rules`
- `portfolio_alert_events`
- `portfolio_calendar_events`

Positions default to `source=manual`. Quantity, cost basis, and cost currency may be missing so pure watch portfolios are supported. Base currency does not trigger automatic FX conversion.

## Boundaries

No broker credentials, account sync, external order state, or automated execution are stored.
