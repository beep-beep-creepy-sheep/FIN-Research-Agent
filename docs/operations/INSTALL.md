# Install

FIN Research Agent is a local-first research terminal. It is not a broker, trading robot, or investment recommendation engine.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pip install -e 'backend[dev]'
cd frontend && npm ci
```

Copy example environment files:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

Run services:

```bash
make api
make worker
make web
```

Use PostgreSQL for production-like runs. SQLite remains supported for local development and tests.

## Deployment Shape

Stage 8 uses documented local deployment rather than adding Docker as a required path. The current app has a Python API/worker, a Next.js frontend, local storage directories, and PostgreSQL/SQLite configuration; keeping deployment as explicit local commands avoids adding a new container maintenance surface for the release candidate.

## Default-Off Features

LLM narration, live official-source smoke tests, and external internet connectors are opt-in. They are not required for tests, e2e, or release smoke.
