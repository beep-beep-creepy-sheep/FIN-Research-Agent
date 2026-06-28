from __future__ import annotations

from fastapi.testclient import TestClient

from app.models import CompanyRecord, FinancialFact, PriceRecord
from finresearch.api.main import app
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.analysis import AnalysisService, IndustryPackRegistry


def _setup_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'library.sqlite'}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOW_TEST_DATA_SOURCES", "true")


def _company(symbol: str = "600519", industry: str = "食品制造") -> None:
    CompanyRepository().upsert(
        CompanyRecord(
            symbol=symbol,
            exchange="SSE",
            company_name=f"{symbol} Corp",
            industry=industry,
            currency="CNY",
        )
    )


def _fact(
    symbol: str,
    code: str,
    value: float,
    period_start: str,
    period_end: str,
    publication_date: str,
    statement_type: str,
    *,
    report_type: str = "annual",
) -> FinancialFact:
    return FinancialFact(
        symbol=symbol,
        metric_code=code,
        metric_name=code,
        value=value,
        unit="CNY",
        currency="CNY",
        period_start=period_start,
        period_end=period_end,
        publication_date=publication_date,
        report_type=report_type,
        statement_type=statement_type,
        source_url=f"https://issuer.example/{symbol}/{period_end}/{code}",
        source_page=1,
        data_source="fixture",
        retrieved_at="2026-06-28T00:00:00+00:00",
    )


def _load_basic_company(symbol: str = "600519", industry: str = "食品制造") -> None:
    _company(symbol, industry)
    FinancialFactRepository().upsert_many(
        [
            _fact(symbol, "total_equity", 100.0, "2024-01-01", "2024-12-31", "2025-04-01", "balance_sheet"),
            _fact(symbol, "total_assets", 200.0, "2024-01-01", "2024-12-31", "2025-04-01", "balance_sheet"),
            _fact(symbol, "revenue", 120.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            _fact(symbol, "gross_profit", 60.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            _fact(symbol, "operating_profit", 30.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            _fact(symbol, "net_profit", 24.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            _fact(symbol, "net_profit_parent", 24.0, "2025-01-01", "2025-12-31", "2026-04-01", "profit_sheet"),
            _fact(symbol, "total_equity", 120.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            _fact(symbol, "total_assets", 240.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            _fact(symbol, "current_assets", 80.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            _fact(symbol, "current_liabilities", 40.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            _fact(symbol, "total_liabilities", 90.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            _fact(symbol, "operating_cash_flow", 28.0, "2025-01-01", "2025-12-31", "2026-04-01", "cash_flow"),
            _fact(symbol, "capital_expenditure", -8.0, "2025-01-01", "2025-12-31", "2026-04-01", "cash_flow"),
            _fact(symbol, "interest_bearing_debt", 20.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            _fact(symbol, "cash_and_equivalents", 50.0, "2025-01-01", "2025-12-31", "2026-04-01", "balance_sheet"),
            _fact(symbol, "revenue", 999.0, "2026-01-01", "2026-12-31", "2027-04-01", "profit_sheet"),
        ]
    )
    PriceRepository().upsert_many(
        [
            PriceRecord(symbol=symbol, trade_date="2026-06-26", close=10.0, adjustment_type="qfq", data_source="fixture_price", retrieved_at="2026-06-28T00:00:00+00:00"),
            PriceRecord(symbol=symbol, trade_date="2026-06-27", close=11.0, adjustment_type="qfq", data_source="fixture_price", retrieved_at="2026-06-28T00:00:00+00:00"),
        ]
    )


def test_industry_pack_registry_selects_expected_packs() -> None:
    registry = IndustryPackRegistry()
    bank_context = type("Context", (), {"industry": "商业银行"})()
    consumer_context = type("Context", (), {"industry": "食品制造"})()
    unknown_context = type("Context", (), {"industry": None})()

    assert registry.select(None, bank_context, "auto") == ("general", "bank")  # type: ignore[arg-type]
    assert registry.select(None, consumer_context, "auto") == ("general", "consumer_manufacturing")  # type: ignore[arg-type]
    assert registry.select(None, unknown_context, "auto") == ("general",)  # type: ignore[arg-type]


def test_general_consumer_analysis_has_lineage_markdown_and_no_advice_terms(tmp_path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    _load_basic_company()

    report = AnalysisService().build("600519", as_of_date="2026-06-28", strict_as_of=True, include_markdown=True)
    payload = report.to_dict()

    assert payload["financial_profile"]["industry_packs"] == ("general", "consumer_manufacturing")
    assert payload["growth"]["findings"]
    assert payload["evidence_map"]
    assert payload["markdown"]
    text = str(payload).lower()
    assert "target price" not in text
    assert "买入" not in text
    assert "卖出" not in text


def test_strict_as_of_excludes_future_facts(tmp_path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    _load_basic_company()

    report = AnalysisService().build("600519", as_of_date="2026-06-28", strict_as_of=True)
    assert "2026-12-31" not in report.context.financial_periods


def test_bank_pack_reports_industrial_metrics_not_applied(tmp_path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    _load_basic_company(symbol="601398", industry="商业银行")

    report = AnalysisService().build("601398", as_of_date="2026-06-28", industry_pack="auto")

    assert report.financial_profile["industry_packs"] == ("general", "bank")
    assert report.industry_specific.section_id == "industry_bank"
    assert any("not applied to banks" in item for item in report.industry_specific.limitations)


def test_analysis_api_empty_company_and_report_options(tmp_path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    client = TestClient(app)

    missing = client.get("/v1/companies/NOPE/analysis")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "company_not_found"

    _load_basic_company()
    response = client.get("/v1/companies/600519/analysis?strict_as_of=true&as_of_date=2026-06-28&include_markdown=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["markdown"]
    assert payload["context"]["strict_as_of"] is True
    assert payload["evidence_map"]

    findings = client.get("/v1/companies/600519/analysis/findings?as_of_date=2026-06-28")
    assert findings.status_code == 200
    assert len(findings.json()["findings"]) >= len(payload["key_findings"])


def test_analysis_quality_and_run_endpoints(tmp_path, monkeypatch) -> None:
    _setup_db(tmp_path, monkeypatch)
    _load_basic_company()
    client = TestClient(app)

    quality = client.get("/v1/companies/600519/analysis/quality")
    assert quality.status_code == 200
    assert any(score["score_id"] == "overall_research_quality_score" for score in quality.json()["scores"])

    run = client.post("/v1/analysis-runs", json={"symbol": "600519", "include_evidence": False})
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert run.json()["report"]["evidence_map"] == []
