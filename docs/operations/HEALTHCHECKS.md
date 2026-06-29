# Healthchecks

Endpoints:

- `GET /health`: process liveness.
- `GET /ready`: config, database, and storage readiness.
- `GET /version`: package version and release stage.
- `GET /v1/system/status`: redacted system status.
- `GET /v1/system/config-check`: production-readiness configuration validation.

Responses do not expose secrets, full environment variables, or local absolute paths. Failed readiness returns HTTP 503 with actionable check codes.

