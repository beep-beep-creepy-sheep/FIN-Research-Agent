.PHONY: setup start test lint api worker web postgres-config

setup:
	cd frontend && npm install

start:
	python3 scripts/launch.py

test:
	PYTHONPATH=.:backend/src pytest -q

lint:
	ruff check .

api:
	PYTHONPATH=.:backend/src uvicorn finresearch.api.main:app --reload --host 127.0.0.1 --port 8000

worker:
	PYTHONPATH=.:backend/src python -m finresearch.worker

web:
	cd frontend && npm run dev

postgres-config:
	python3 scripts/configure_postgres.py
