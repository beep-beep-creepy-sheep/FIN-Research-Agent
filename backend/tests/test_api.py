from fastapi.testclient import TestClient

from finresearch.api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_localhost_and_loopback_frontends() -> None:
    client = TestClient(app)

    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.options(
            "/v1/screener/query",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


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
    assert payload[0]["frequency"] == "daily"
    assert payload[0]["currency"] == "CNY"
    assert payload[0]["quality_status"] == "empty"


def test_company_chart_alias_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.get("/v1/companies/600519/chart")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "kline_volume"


def test_metrics_api_successful_financial_results_have_fact_lineage_and_strict_as_of(tmp_path, monkeypatch) -> None:
    from app.models import FinancialFact
    from finresearch.metrics import list_metric_definitions
    from finresearch.repositories.financial_facts import FinancialFactRepository

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")

    def fact(
        metric_code: str,
        metric_name: str,
        value: float,
        period_start: str,
        period_end: str,
        publication_date: str,
        statement_type: str,
    ) -> FinancialFact:
        return FinancialFact(
            symbol="600519",
            metric_code=metric_code,
            metric_name=metric_name,
            value=value,
            period_start=period_start,
            period_end=period_end,
            publication_date=publication_date,
            report_type="annual",
            statement_type=statement_type,
            is_consolidated=True,
            source_url=f"https://issuer.example/{period_end}/{metric_code}",
            data_source="fixture",
            retrieved_at="2026-06-26T00:00:00+00:00",
        )

    FinancialFactRepository().upsert_many(
        [
            fact("total_equity", "所有者权益", 100.0, "2024-01-01", "2024-12-31", "2025-04-01", "balance_sheet"),
            fact("revenue", "营业收入", 120.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            fact("gross_profit", "毛利润", 54.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            fact("net_profit", "净利润", 24.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            fact("total_equity", "所有者权益", 120.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            fact("current_assets", "流动资产", 80.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            fact("current_liabilities", "流动负债", 40.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            fact("revenue", "营业收入", 999.0, "2026-01-01", "2026-12-31", "2027-04-01", "profit_sheet"),
            fact("gross_profit", "毛利润", 999.0, "2026-01-01", "2026-12-31", "2027-04-01", "profit_sheet"),
        ]
    )
    client = TestClient(app)

    response = client.get("/v1/companies/600519/metrics?as_of=2026-06-26")

    assert response.status_code == 200
    definitions = {definition.code: definition for definition in list_metric_definitions()}
    successful_financial = [
        item
        for item in response.json()
        if definitions[item["code"]].calculation_domain == "financial" and item["value"] is not None
    ]
    assert successful_financial
    assert all(item["source_fact_ids"] for item in successful_financial)
    gross_margin = next(item for item in successful_financial if item["code"] == "gross_margin")
    assert gross_margin["period_end"] == "2025-12-31"
    assert gross_margin["source_urls"] == [
        "https://issuer.example/2025-12-31/gross_profit",
        "https://issuer.example/2025-12-31/revenue",
    ]


def test_screener_query_uses_local_financial_facts(tmp_path, monkeypatch) -> None:
    from app.models import CompanyRecord, FinancialFact
    from finresearch.repositories.companies import CompanyRepository
    from finresearch.repositories.financial_facts import FinancialFactRepository

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    CompanyRepository().upsert(
        CompanyRecord(symbol="600519", company_name="贵州茅台", exchange="SSE", industry="白酒")
    )
    CompanyRepository().upsert(
        CompanyRecord(symbol="000001", company_name="平安银行", exchange="SZSE", industry="银行")
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
            FinancialFact(
                symbol="000001",
                metric_code="revenue",
                metric_name="营业收入",
                value=200.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
            FinancialFact(
                symbol="000001",
                metric_code="net_profit_parent",
                metric_name="归母净利润",
                value=10.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
        ]
    )
    client = TestClient(app)

    broad_response = client.post("/v1/screener/query", json={"min_net_margin": 0})
    assert broad_response.status_code == 200
    assert {row["symbol"] for row in broad_response.json()["rows"]} == {"000001", "600519"}

    response = client.post("/v1/screener/query", json={"min_net_margin": 0.2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["as_of"] == "2025-12-31"
    assert payload["rows"][0]["symbol"] == "600519"

    alias_response = client.post("/v1/screens/query", json={"min_net_margin": 0.2})
    assert alias_response.status_code == 200
    assert alias_response.json()["rows"][0]["symbol"] == "600519"


def test_screener_rejects_invalid_sort(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    client = TestClient(app)

    response = client.post("/v1/screener/query", json={"sort_by": "not_a_metric"})

    assert response.status_code == 400


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
    assert response.json()["status"] == "queued"
    assert response.json()["job_status"] == "queued"
    assert calls["mcporter"] == 0


def test_research_run_status_and_get_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("LLM_ENABLED", "false")
    client = TestClient(app)

    created = client.post("/v1/research-runs", json={"symbol": "600519", "years": 5}).json()
    run_id = created["research_run_id"]

    status = client.get(f"/v1/research-runs/{run_id}/status")
    detail = client.get(f"/v1/research-runs/{run_id}")

    assert status.status_code == 200
    assert status.json()["status"] == "queued"
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id
