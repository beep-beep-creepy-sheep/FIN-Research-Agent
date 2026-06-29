# Configuration

Settings are read from environment variables, with local `.env` files used only for local convenience. Do not commit real API keys, cookies, tokens, broker credentials, or private report downloads.

## Required Production Settings

- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>`
- `CORS_ORIGINS=<trusted frontend origin>`
- `DATA_DIR`, `DOCUMENTS_DIR`, `RAW_DATA_DIR`, `REPORTS_DIR`

Production validation fails if SQLite is used, if CORS contains `*`, or if live official sources are enabled without explicit live-smoke opt-in.

## Safe Defaults

- `LLM_ENABLED=false`
- `RUN_LIVE_SOURCE_TESTS=false`
- `AGENT_REACH_ENABLED=false`
- `EXA_ENABLED=false`
- `OFFICIAL_SOURCE_MODE=fixture` outside production, `disabled` in production when unset

Run:

```bash
make config-check
curl http://localhost:8000/v1/system/config-check
```

Config summaries redact secrets and do not expose local absolute paths.

