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


def test_create_market_snapshot_job_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.post("/v1/jobs", json={"job_type": "market_snapshot", "market": "CN"})

    assert response.status_code == 200
    assert response.json()["job_type"] == "market_snapshot"


def test_connectors_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.get("/v1/connectors")

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert "direct_web" in names
    assert "agent_reach_exa" in names
    assert "agent_reach_twitter" in names


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


def test_market_overview_empty_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.get("/v1/market/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["empty"] is True
    assert payload["snapshot"]["status"] == "no_snapshot"
    assert len(payload["charts"]) == 6


def test_company_charts_endpoint_empty_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.get("/v1/companies/600519/charts")

    assert response.status_code == 200
    payload = response.json()
    assert [chart["id"] for chart in payload] == [
        "kline_volume",
        "financial_trend",
        "margin_trend",
        "returns_trend",
        "valuation_band",
    ]
    assert payload[0]["empty"] is True


def test_screener_query_uses_local_financial_facts(tmp_path, monkeypatch) -> None:
    from app.models import CompanyRecord, FinancialFact
    from finresearch.repositories.companies import CompanyRepository
    from finresearch.repositories.financial_facts import FinancialFactRepository

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    CompanyRepository().upsert(
        CompanyRecord(symbol="600519", company_name="贵州茅台", exchange="SSE", industry="白酒")
    )
    FinancialFactRepository().upsert_many(
        [
            FinancialFact(
                symbol="600519",
                metric_code="revenue",
                metric_name="营业收入",
                value=100.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
            FinancialFact(
                symbol="600519",
                metric_code="net_profit_parent",
                metric_name="归母净利润",
                value=30.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
        ]
    )
    client = TestClient(app)

    response = client.post("/v1/screener/query", json={"min_net_margin": 0.2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["rows"][0]["symbol"] == "600519"


def test_research_with_exa_disabled_does_not_call_mcporter(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("AGENT_REACH_ENABLED", "true")
    monkeypatch.setenv("EXA_ENABLED", "false")
    monkeypatch.setenv("LLM_ENABLED", "false")
    calls = {"mcporter": 0}

    def fake_search(*_args, **_kwargs):
        calls["mcporter"] += 1
        raise AssertionError("mcporter should not be called when EXA_ENABLED=false")

    monkeypatch.setattr(
        "finresearch.connectors.agent_reach.client.AgentReachCommandClient.exa_search",
        fake_search,
    )
    monkeypatch.setattr(
        "finresearch.connectors.rss.RSSConnector.search",
        lambda *_args, **_kwargs: [],
    )
    client = TestClient(app)

    response = client.post("/v1/research-runs", json={"symbol": "600519", "years": 5})

    assert response.status_code == 200
    assert calls["mcporter"] == 0
