# Backend working agreement

## Scope
The backend is a FastAPI + SQLAlchemy application. Keep PostgreSQL as the primary runtime
database and SQLite as a test/compatibility target. Migrations may be lightweight while the
project has no Alembic directory, but model changes must be documented in the final response.

## Data rules
- Financial facts, prices, market snapshots, metric observations, citations, and connector output
  must be traceable to a source or explicitly marked unavailable.
- Do not persist fake, sampled, randomized, or UI placeholder market data.
- Community and social sources are leads only unless corroborated by primary or authoritative
  sources.
- Preserve `as_of`, publication dates, retrieved timestamps, units, currencies, source URLs, local
  snapshot paths, and content hashes whenever they exist.

## Calculation rules
- All financial calculations belong in deterministic Python services with tests.
- LLM providers may summarize, classify, or narrate evidence; they must not calculate, backfill,
  invent, or modify financial facts.
- Metric definitions must declare formula text, inputs, periodicity, units, category, source
  requirements, and missing-data behavior.

## API and worker rules
- Do not remove existing CLI commands, API routes, or repository methods unless the user explicitly
  asks.
- Long-running work must use database jobs and Python workers, not synchronous request blocking.
- External connectors must have short timeouts, fast skip states, and connector-local failure
  isolation.
- Connector credentials and cookies must never be returned to the frontend or written to logs.

## Tests
- Add or update unit, repository, API, worker, timeout, and data-quality tests for backend behavior.
- Run `PYTHONPATH=.:backend/src pytest -q` and `ruff check .` after backend changes.
