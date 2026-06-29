# Release Checklist

- Stage 8 gate passes from current `main`.
- Work starts on `feature/stage-8-production-security-release`.
- `PYTHONPATH=.:backend/src pytest -q`
- `PYTHONPATH=.:backend/src pytest -q backend/tests/test_stage8_production_security.py`
- `ruff check .`
- `PYTHONPATH=.:backend/src python -m mypy backend/src/finresearch`
- `cd frontend && npm test`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- Playwright Chromium e2e passes.
- `make sqlite-alembic-smoke`
- PostgreSQL Alembic smoke passes or is marked `BLOCKED_LOCAL_TOOLING`.
- `make config-check`
- `make release-smoke`
- `make tracked-secret-file-check`
- `make secret-scan`
- `make python-audit`
- `cd frontend && npm audit --audit-level=high`
- GitHub Actions backend/frontend/e2e are green.
- `docs/PROJECT_STATE.md` records final Stage 8 status.
- Working tree is clean and local branch is synced with remote.

