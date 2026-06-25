from fastapi.testclient import TestClient

from finresearch.api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_job_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.post("/v1/jobs", json={"symbol": "600519", "years": 5})

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
