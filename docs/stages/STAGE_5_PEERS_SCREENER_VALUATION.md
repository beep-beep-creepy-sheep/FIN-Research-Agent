# Stage 5: Peers, Screener, Valuation Lab

Stage 5 upgrades the local research terminal from single-company professional analysis to peer comparison, richer screening, and a deterministic valuation lab.

## Implemented

- Peer set selection from local company metadata, industry, exchange, listing board, and manual overrides.
- Peer metrics matrix with rank, percentile, z-score, missing reasons, not-applicable states, and transparent outlier flags.
- Screener filters for market, exchange, board, growth, margin, returns, leverage, valuation, missing-data inclusion, presets, and JSON/CSV export.
- Relative valuation using PE TTM, EV/EBITDA, FCF yield, PB, and PS where available.
- Simplified DCF / owner earnings scenarios with base, bear, and bull assumptions, safety bounds, sensitivity tables, evidence, and limitations.
- Valuation run persistence with deterministic run IDs and no silent overwrite.
- Company page Peers, Peer Metrics Matrix, and Valuation Lab panels.

## Not Implemented

Stage 5 does not add AI orchestration, institutional report generation, portfolio management, broker login, automatic trading, price prediction, paid APIs, or target-price style recommendations.

## Guardrails

All outputs are deterministic Python calculations over local data. Missing values remain missing. The valuation lab outputs scenario ranges, relative positions, assumptions, sensitivity, and limitations only. It is not investment advice.

## Stage 6 Hand-Off

Stage 6 can consume peer sets, valuation runs, evidence maps, and limitations as structured inputs for later report orchestration. It must keep the same non-advice and no target-price boundaries.
