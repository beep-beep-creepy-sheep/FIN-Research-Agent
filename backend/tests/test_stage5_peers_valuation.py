from __future__ import annotations

from fastapi.testclient import TestClient

from app.models import CompanyRecord, FinancialFact, PriceRecord
from finresearch.api.main import app
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.valuation import PeerMetricsMatrixService, PeerSetService, ValuationLabService


def _setup(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'stage5.sqlite'}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOW_TEST_DATA_SOURCES", "true")


def _company(symbol: str, industry: str, exchange: str = "SSE") -> None:
    CompanyRepository().upsert(
        CompanyRecord(symbol=symbol, company_name=f"{symbol} Corp", exchange=exchange, industry=industry)
    )


def _fact(symbol: str, code: str, value: float, period_end: str = "2025-12-31") -> FinancialFact:
    statement = "balance_sheet" if code in {"total_assets", "total_liabilities", "total_equity", "cash_and_equivalents", "interest_bearing_debt", "shares_outstanding", "current_assets", "current_liabilities"} else "profit_sheet"
    if code in {"operating_cash_flow", "capital_expenditure"}:
        statement = "cash_flow"
    return FinancialFact(
        symbol=symbol,
        metric_code=code,
        metric_name=code,
        value=value,
        unit="CNY",
        currency="CNY",
        period_start="2025-01-01",
        period_end=period_end,
        publication_date="2026-04-01",
        report_type="annual",
        statement_type=statement,
        source_url=f"https://issuer.example/{symbol}/{code}",
        source_page=1,
        data_source="fixture",
        retrieved_at="2026-06-28T00:00:00+00:00",
    )


def _load_company(symbol: str, industry: str, revenue: float, profit: float, *, exchange: str = "SSE") -> None:
    _company(symbol, industry, exchange)
    facts = [
        _fact(symbol, "revenue", revenue),
        _fact(symbol, "gross_profit", revenue * 0.45),
        _fact(symbol, "operating_profit", profit * 1.2),
        _fact(symbol, "net_profit", profit),
        _fact(symbol, "net_profit_parent", profit),
        _fact(symbol, "total_assets", revenue * 2),
        _fact(symbol, "total_liabilities", revenue * 0.6),
        _fact(symbol, "total_equity", revenue * 1.4),
        _fact(symbol, "current_assets", revenue * 0.5),
        _fact(symbol, "current_liabilities", revenue * 0.25),
        _fact(symbol, "operating_cash_flow", profit * 1.1),
        _fact(symbol, "capital_expenditure", -revenue * 0.08),
        _fact(symbol, "interest_bearing_debt", revenue * 0.2),
        _fact(symbol, "cash_and_equivalents", revenue * 0.1),
        _fact(symbol, "shares_outstanding", 10.0),
        _fact(symbol, "market_cap", revenue * 3),
        _fact(symbol, "ebitda", profit * 1.5),
        _fact(symbol, "revenue", revenue * 0.9, "2024-12-31"),
        _fact(symbol, "net_profit_parent", profit * 0.9, "2024-12-31"),
    ]
    FinancialFactRepository().upsert_many(facts)
    PriceRepository().upsert_many(
        [
            PriceRecord(symbol=symbol, trade_date=f"2026-05-{day:02d}", close=10 + day / 10, adjustment_type="qfq", data_source="fixture_price", retrieved_at="2026-06-28T00:00:00+00:00")
            for day in range(1, 29)
        ]
    )


def _load_fixture() -> None:
    _load_company("600519", "食品制造", 1000, 220)
    _load_company("600000", "食品制造", 800, 120)
    _load_company("600001", "食品制造", 900, 130)
    _load_company("600002", "食品制造", 1100, 160)
    _load_company("000001", "商业银行", 1200, 210, exchange="SZSE")


def test_peer_selection_same_industry_manual_exclude_and_no_bank_mixing(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_fixture()

    result = PeerSetService().build("600519", manual_peers=["600002"], exclude_symbols=["600001"])

    assert "600002" in result.selected_symbols
    assert "600001" not in result.selected_symbols
    assert "000001" not in result.selected_symbols
    assert all(candidate.reason for candidate in result.candidates)
    assert any(candidate.source == "manual" for candidate in result.candidates)


def test_unknown_industry_returns_insufficient_peer_data(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _company("NOIND", "")

    result = PeerSetService().build("NOIND")

    assert "insufficient_peer_data" in result.quality_flags
    assert result.selected_symbols == ()


def test_peer_metrics_rank_percentile_outlier_and_missing(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_fixture()

    matrix = PeerMetricsMatrixService().build(
        "600519",
        peer_symbols=["600000", "600001", "600002"],
        metric_codes=["revenue", "roe", "fcf_yield"],
        as_of_date="2026-06-28",
        strict_as_of=True,
    )

    target_revenue = matrix["rows"][0]["metrics"]["revenue"]
    assert target_revenue["rank"] == 2
    assert target_revenue["percentile"] is not None
    assert "z_score" in target_revenue
    assert matrix["outlier_policy"]


def test_relative_and_dcf_valuation_no_target_price_wording(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_fixture()

    relative = ValuationLabService().run("600519", model_type="relative_valuation", as_of_date="2026-06-28")
    dcf = ValuationLabService().run("600519", model_type="dcf_owner_earnings", as_of_date="2026-06-28")

    text = f"{relative} {dcf}".lower()
    assert relative["not_investment_advice"] is True
    assert dcf["not_investment_advice"] is True
    assert "目标价" not in text
    assert "target price" not in text
    assert "buy" not in text
    assert "sell" not in text
    assert relative["valuation_run_id"] == ValuationLabService().run("600519", model_type="relative_valuation", as_of_date="2026-06-28")["valuation_run_id"]


def test_dcf_assumption_hash_changes_and_bounds(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_fixture()
    service = ValuationLabService()

    base = service.run("600519", model_type="dcf_owner_earnings", as_of_date="2026-06-28", assumptions={"discount_rate": 0.1})
    changed = service.run("600519", model_type="dcf_owner_earnings", as_of_date="2026-06-28", assumptions={"discount_rate": 0.11})

    assert base["valuation_run_id"] != changed["valuation_run_id"]
    assert base["sensitivity"]["table"]
    client = TestClient(app)
    response = client.post(
        "/v1/companies/600519/valuation",
        json={"model_type": "dcf_owner_earnings", "assumptions": {"discount_rate": 0.01}},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "discount_rate_out_of_bounds"


def test_stage5_api_and_screener_preset_export(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_fixture()
    client = TestClient(app)

    assert client.get("/v1/companies/600519/peers?as_of_date=2026-06-28").status_code == 200
    assert client.post("/v1/companies/600519/peer-metrics", json={"metric_codes": ["revenue", "roe"]}).status_code == 200
    valuation = client.get("/v1/companies/600519/valuation?model_type=relative_valuation")
    assert valuation.status_code == 200
    run_id = valuation.json()["valuation_run_id"]
    assert client.get(f"/v1/valuation/runs/{run_id}").status_code == 200
    assert client.get("/v1/companies/600519/valuation/runs").json()

    query = client.post("/v1/screener/query", json={"min_revenue": 1, "include_missing": True, "sort_by": "market_cap"})
    assert query.status_code == 200
    assert query.json()["rows"][0]["data_quality_status"] in {"available", "partial"}
    preset = client.post("/v1/screener/presets", json={"name": "quality-growth", "filters": {"min_roe": 0.1}})
    assert preset.status_code == 200
    assert client.get("/v1/screener/presets").json()[0]["name"] == "quality-growth"
    assert client.get("/v1/screener/export?fmt=json").status_code == 200
    csv_response = client.get("/v1/screener/export?fmt=csv")
    assert csv_response.status_code == 200
    assert "symbol,company_name" in csv_response.text
