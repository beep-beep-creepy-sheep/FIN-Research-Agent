# Stage 8 Production Security Release

Status: PARTIAL_LOCAL, pending final full regression and GitHub Actions verification.

Stage 8 hardens FIN Research Agent as a local-first release candidate. It does not add new research modules, broker access, automatic trading, target prices, paid APIs, Redis, Celery, Kafka, Elasticsearch, or SaaS tenancy.

## Implemented Scope

- Central settings validation in `finresearch.settings`.
- Redacted configuration summary for startup and health checks.
- `finresearch-backend config-check` / `python -m finresearch.cli.main config-check`.
- System endpoints: `/health`, `/ready`, `/version`, `/v1/system/status`, `/v1/system/config-check`.
- Structured API error responses with request IDs and local path redaction.
- Pagination/query limits for screener export, document chunk/search, portfolio holdings/watch items/alert events, and calendar events.
- Stage 8 focused tests for config, redaction, health/readiness/version/status, structured errors, path traversal, SSRF guard, report export escaping, and forbidden advice/trading wording.
- CI hooks for Stage 8 tests, config smoke, release smoke, repeated SQLite Alembic upgrade, secret scan, Python audit, and npm high-severity audit.

## Release Gate

Final RC requires full local quality gates plus successful GitHub Actions backend/frontend/e2e for the Stage 8 branch. PostgreSQL migration verification must be reported as PASS only when local PostgreSQL tooling is available; otherwise record `BLOCKED_LOCAL_TOOLING`.

