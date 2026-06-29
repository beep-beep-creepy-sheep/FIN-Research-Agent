from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def main() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="finresearch-release-smoke-"))
    os.environ.update(
        {
            "APP_ENV": "test",
            "DATA_DIR": str(temp_dir),
            "DOCUMENTS_DIR": str(temp_dir / "documents"),
            "RAW_DATA_DIR": str(temp_dir / "raw"),
            "REPORTS_DIR": str(temp_dir / "reports"),
            "DATABASE_URL": f"sqlite:///{temp_dir / 'release-smoke.sqlite'}",
            "LLM_ENABLED": "false",
            "OFFICIAL_SOURCE_MODE": "fixture",
            "RUN_LIVE_SOURCE_TESTS": "false",
        }
    )
    for name in ("OPENAI_API_KEY",):
        os.environ.pop(name, None)

    from finresearch.api.main import app

    client = TestClient(app)
    checks = {
        "health": client.get("/health"),
        "ready": client.get("/ready"),
        "version": client.get("/version"),
        "config": client.get("/v1/system/config-check"),
        "status": client.get("/v1/system/status"),
        "screener": client.post("/v1/screener/query", json={"limit": 5}),
        "portfolios": client.get("/v1/portfolios"),
    }
    failed = {name: response.status_code for name, response in checks.items() if response.status_code >= 400}
    if failed:
        raise SystemExit(f"release smoke failed: {failed}")
    print("release smoke passed")


if __name__ == "__main__":
    main()
