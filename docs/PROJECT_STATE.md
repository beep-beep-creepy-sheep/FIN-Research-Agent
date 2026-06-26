# Project State

Updated: 2026-06-26

## Snapshot

- Stage 1 status: PASS locally.
- Stage 2 status: PASS locally.
- Current branch: main.
- Current commit: pending local anti-shortcut audit commits; pre-audit HEAD was b87f6ef0397a590a5014628ec0436ef3ecc413eb.
- origin/main commit at audit start: b87f6ef0397a590a5014628ec0436ef3ecc413eb.
- GitHub Actions true status: UNVERIFIED until pushed commits complete backend, frontend, and e2e jobs.

## Local Gates

- Python tests: PASS, `PYTHONPATH=.:backend/src pytest -q`, 64 passed.
- Ruff: PASS, `ruff check .`.
- Real Python type check: PASS, `PYTHONPATH=.:backend/src python -m mypy backend/src/finresearch`, 74 files, 0 errors.
- Frontend tests: PASS, `npm test`, 11 passed.
- Frontend TypeScript: PASS, `npx tsc --noEmit`.
- Frontend build: PASS, `npm run build`.
- Playwright: PASS, `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run test:e2e -- --project=chromium`, 4 passed.
- Alembic SQLite empty upgrade: PASS, `ALEMBIC_DATABASE_URL=sqlite:////tmp/finresearch-empty.sqlite PYTHONPATH=.:backend/src alembic upgrade head`.
- Alembic PostgreSQL current DB upgrade and repeated upgrade: PASS using `backend/.env` PostgreSQL URL.
- Alembic PostgreSQL temporary empty DB upgrade and repeated upgrade: PASS; temporary database created and dropped by the audit script.
- FastAPI smoke: PASS, `curl -fsS http://127.0.0.1:8000/health`.
- Worker smoke: PASS, queued research and market snapshot jobs completed through `finresearch.worker.run_once`.
- Background research: PASS with insufficient structured data state and explicit data gaps.
- MarketSnapshot: PASS with `insufficient_data` empty state and source metadata.
- tracked-secret-file-check: PASS; this is only tracked-file pattern grep, not a full security scan.
- Secret scan: PASS, `detect-secrets findings: 0`.
- Python dependency audit: PASS for project-declared dependencies via `make python-audit`.
- npm dependency audit: PARTIAL; 2 moderate findings in `next` via bundled `postcss`, no high/critical findings. Available audit fix is breaking (`npm audit fix --force` would install `next@9.3.3`), so no force upgrade was applied.

## Stage Components

- Alembic: explicit initial migration now uses `op.create_table`, indexes, unique constraints, and foreign keys; no longer imports runtime `Base.metadata.create_all()`.
- Background research: queued API path creates a `research_run` and a database job; worker marks completed/failed and preserves actionable errors.
- MarketSnapshot: real local data only; missing local quotes produce `insufficient_data` rather than fabricated charts.
- Metric registry: 41 definitions registered. Formula audit distinguishes real implementations from unavailable/partial metrics in `docs/audits/STAGE_1_2_AUDIT.md`.

## Known Limitations

- GitHub Actions status for this new local work is UNVERIFIED until commits are pushed and queried.
- Revenue TTM, FCF Yield, Net Debt / EBITDA, PE TTM, EV / EBITDA, Beta, Alpha, annualized volatility, and maximum drawdown are not implemented and must not be presented as calculated.
- `revenue_yoy` compares adjacent rows in the matrix and does not yet enforce annual-vs-quarter comparability or cumulative-quarter normalization.
- Direct web connector still permits arbitrary HTTP(S) reads; SSRF hardening is basic and should be tightened before exposing beyond localhost.
- npm audit moderate issue is in Next's transitive PostCSS dependency; no non-breaking npm audit fix was available in this run.

## Next Step

- Push the audit commits and verify real GitHub Actions backend, frontend, and e2e jobs before Stage 3 begins.
