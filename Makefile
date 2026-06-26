.PHONY: setup start test lint typecheck tracked-secret-file-check secret-scan python-audit api worker web postgres-config

setup:
	cd frontend && npm install

start:
	python3 scripts/launch.py

test:
	PYTHONPATH=.:backend/src pytest -q

lint:
	ruff check .

typecheck:
	PYTHONPATH=.:backend/src python -m mypy backend/src/finresearch

tracked-secret-file-check:
	@if git grep -n -I -E '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----)' -- ':!frontend/package-lock.json' ':!frontend/node_modules' ':!docs'; then \
		echo "tracked-secret-file-check found secret-like tracked text"; \
		exit 1; \
	else \
		status=$$?; \
		if [ $$status -eq 1 ]; then echo "tracked-secret-file-check found no secret-like tracked text"; else exit $$status; fi; \
	fi

secret-scan:
	@detect-secrets scan --all-files --exclude-files '(^frontend/node_modules/|^frontend/\.next/|^data/|^\.git/|^\.mypy_cache/|^\.pytest_cache/|^\.ruff_cache/|^backend/\.pytest_cache/|^backend/\.ruff_cache/)' > /tmp/finresearch-detect-secrets.json
	@python -c 'import json,sys; data=json.load(open("/tmp/finresearch-detect-secrets.json")); results=data.get("results", {}); print(f"detect-secrets findings: {sum(len(v) for v in results.values())}"); sys.exit(1 if results else 0)'

python-audit:
	@python -c 'import tomllib; from pathlib import Path; seen=[]; [seen.append(dep) for path in [Path("pyproject.toml"), Path("backend/pyproject.toml")] for dep in tomllib.loads(path.read_text()).get("project", {}).get("dependencies", []) + tomllib.loads(path.read_text()).get("project", {}).get("optional-dependencies", {}).get("dev", []) if dep not in seen]; Path("/tmp/finresearch-requirements.txt").write_text("\n".join(seen) + "\n")'
	python -m pip_audit -r /tmp/finresearch-requirements.txt

api:
	PYTHONPATH=.:backend/src uvicorn finresearch.api.main:app --reload --host 127.0.0.1 --port 8000

worker:
	PYTHONPATH=.:backend/src python -m finresearch.worker

web:
	cd frontend && npm run dev

postgres-config:
	python3 scripts/configure_postgres.py
