# Scenario DCF / Owner Earnings

The Stage 5 DCF is a simplified owner earnings scenario model.

Inputs:

- Historical revenue.
- FCF or owner earnings.
- FCF margin.
- Net debt if available.
- Shares outstanding only when locally sourced.

Scenarios:

- `bear`
- `base`
- `bull`

Assumption bounds:

- Discount rate: 4% to 25%.
- Terminal growth: -2% to 4%.
- Terminal growth must be below discount rate.
- Projection years: 3 to 10.
- Revenue growth: -20% to 20%.
- FCF margin: -20% to 40%.

If revenue or cash-flow history is insufficient, the model returns `insufficient_cash_flow_history`. Per-share value is omitted unless shares outstanding is available from structured local facts.
