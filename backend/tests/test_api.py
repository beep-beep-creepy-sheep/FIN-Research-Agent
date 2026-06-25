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


def test_connectors_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.get("/v1/connectors")

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "direct_web" in names
    assert "agent_reach" in names


def test_external_sources_search_empty_query_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.post(
        "/v1/external-sources/search",
        json={"query": "not a url", "connectors": ["direct_web"], "limit": 3},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
