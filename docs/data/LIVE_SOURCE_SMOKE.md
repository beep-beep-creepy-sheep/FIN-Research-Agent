# Live Source Smoke

Live source tests are opt-in only:

```bash
RUN_LIVE_SOURCE_TESTS=true PYTHONPATH=.:backend/src pytest -q backend/tests -k live_source
```

Results must be reported as `PASS`, `BLOCKED_BY_NETWORK`, `BLOCKED_BY_ANTI_BOT`, `SOURCE_CHANGED`, `AUTH_REQUIRED`, `RATE_LIMITED`, or `NOT_RUN`. Fixture tests must not be described as live source success.
