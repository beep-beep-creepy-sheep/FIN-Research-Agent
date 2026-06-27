# Live Source Smoke

Live source tests are opt-in only:

```bash
make live-source-smoke
```

Equivalent command:

```bash
PYTHONPATH=.:backend/src RUN_LIVE_SOURCE_TESTS=true OFFICIAL_SOURCE_MODE=live python -m finresearch.cli.live_source_smoke
```

Results must be reported as `PASS`, `BLOCKED_BY_NETWORK`, `BLOCKED_BY_ANTI_BOT`, `RATE_LIMITED`, `SOURCE_CHANGED`, `NOT_IMPLEMENTED`, `NOT_CONFIGURED`, or `FAIL`. Fixture tests must not be described as live source success.

Latest local run on 2026-06-27:

- CNINFO: PASS, symbol `600519`, listed_count 1.
- SSE: NOT_IMPLEMENTED.
- SZSE: NOT_IMPLEMENTED.
- BSE: NOT_IMPLEMENTED.
- SEC EDGAR: NOT_IMPLEMENTED.
