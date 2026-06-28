# Screener Guide

The Stage 5 screener queries local structured financial facts. It does not call live sources and does not fill missing fields with fake data.

Supported filter families:

- Basic metadata: market, exchange, industry, listing board.
- Financials: revenue, growth, margins, ROE, ROIC, FCF yield, leverage, current ratio.
- Valuation: PE TTM, EV/EBITDA, FCF yield, valuation data status.
- Risk and quality placeholders: missing-data inclusion and local quality status.

Missing data:

- `include_missing=false` excludes companies that cannot satisfy a numeric condition.
- `include_missing=true` keeps rows where the filtered metric is missing and marks data quality as partial.

Presets:

- Presets are stored in the local `screen_presets` table.
- Presets save filters only, not API keys or external content.

Export:

- JSON export returns the full structured payload.
- CSV export includes visible result fields and data-quality status.
