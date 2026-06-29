# Known Limitations

- This is a local research terminal, not a brokerage or trading system.
- No broker login, order placement, automatic trading, automatic rebalancing, target price, or buy/sell/hold output.
- LLM narration is optional and defaults off.
- Live official-source smoke is opt-in and is not part of default CI.
- PostgreSQL is the recommended production database; SQLite remains for local development and tests.
- Local PostgreSQL migration verification must be marked `BLOCKED_LOCAL_TOOLING` when PostgreSQL tools are unavailable.
- Moderate npm advisories may remain when the only fix is a breaking forced upgrade.
- External connector availability depends on separately installed optional tools.
