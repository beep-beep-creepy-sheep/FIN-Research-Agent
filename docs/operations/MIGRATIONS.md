# Migrations

Alembic migrations live in `backend/alembic/versions` and must not be rewritten after merge.

## Current Order

1. `0001_initial_schema`
2. `0002_stage2_metadata_fields`
3. `0003_professional_metric_metadata`
4. `0004_stage3_official_source_coverage`
5. `0005_stage5_peers_valuation`
6. `0006_stage6_reports`
7. `0007_stage7_portfolio_risk_alerts`

## SQLite Smoke

```bash
make sqlite-alembic-smoke
```

This upgrades an empty SQLite database to head twice.

## PostgreSQL

Back up before migration, then run:

```bash
ALEMBIC_DATABASE_URL='postgresql+psycopg://<user>:<password>@<host>:5432/<db>' \
  PYTHONPATH=.:backend/src alembic upgrade head
```

If `psql`, `pg_isready`, or local PostgreSQL are unavailable, report `BLOCKED_LOCAL_TOOLING` rather than PASS.

