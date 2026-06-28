from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.models import CompanyRecord, FinancialFact, PriceRecord
from finresearch.api.main import app
from finresearch.database.models import DataQualityIssue, Filing, ReportRun, ValuationRun
from finresearch.database.session import session_scope
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.portfolios import PortfolioRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.portfolio import (
    AlertsService,
    CalendarService,
    PortfolioAnalyticsService,
    PortfolioPerformanceService,
    PortfolioReportService,
    PortfolioRiskService,
    PortfolioService,
)


def _setup(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'stage7.sqlite'}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOW_TEST_DATA_SOURCES", "true")


def _load_symbol(symbol: str = "600519", industry: str = "食品制造", *, prices: bool = True) -> None:
    CompanyRepository().upsert(
        CompanyRecord(symbol=symbol, company_name=f"{symbol} Corp", exchange="SSE", industry=industry, currency="CNY")
    )
    FinancialFactRepository().upsert_many(
        [
            FinancialFact(
                symbol=symbol,
                metric_code="revenue",
                metric_name="revenue",
                value=100.0,
                unit="CNY",
                currency="CNY",
                period_start="2025-01-01",
                period_end="2025-12-31",
                publication_date="2026-04-01",
                report_type="annual",
                statement_type="profit_sheet",
                source_url=f"https://issuer.example/{symbol}/revenue",
                data_source="fixture",
                retrieved_at="2026-06-28T00:00:00+00:00",
            )
        ]
    )
    if prices:
        PriceRepository().upsert_many(
            [
                PriceRecord(
                    symbol=symbol,
                    trade_date=f"2026-05-{day:02d}",
                    close=10 + day / 10,
                    adjustment_type="qfq",
                    data_source="fixture_price",
                    retrieved_at="2026-06-28T00:00:00+00:00",
                )
                for day in range(1, 29)
            ]
        )


def _portfolio() -> int:
    row = PortfolioService().create({"name": "Research Portfolio", "portfolio_type": "manual_holdings"})
    return int(row["id"])


def test_portfolio_repository_crud_manual_source_and_archive(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    portfolio_id = _portfolio()
    repo = PortfolioRepository()

    holding = repo.add_holding(portfolio_id, {"symbol": "600519", "quantity": 10, "cost_basis": 8})
    assert holding["source"] == "manual"
    updated = repo.update_holding(portfolio_id, int(holding["id"]), {"symbol": "600519", "quantity": 12})
    assert updated and updated["quantity"] == 12
    item = repo.add_watch_item(portfolio_id, {"symbol": "000001", "thesis": "research candidate", "tags": ["bank"]})
    assert item["symbol"] == "000001"
    assert repo.update_watch_item(portfolio_id, int(item["id"]), {"symbol": "000001", "interest_level": "medium"})
    assert repo.delete_watch_item(portfolio_id, int(item["id"])) is True
    assert repo.delete_holding(portfolio_id, int(holding["id"])) is True
    assert PortfolioService().archive(portfolio_id) is True
    assert PortfolioService().get(portfolio_id) is None


def test_analytics_exposure_missing_price_and_equal_weight_watchlist(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_symbol("600519", "白酒", prices=True)
    _load_symbol("000001", "银行", prices=False)
    watch = PortfolioService().create({"name": "Watch", "portfolio_type": "watchlist"})
    pid = int(watch["id"])
    repo = PortfolioRepository()
    repo.add_watch_item(pid, {"symbol": "600519"})
    repo.add_watch_item(pid, {"symbol": "000001"})

    summary = PortfolioAnalyticsService().summary(pid)
    exposure = PortfolioAnalyticsService().exposure(pid)

    assert summary["weighting_policy"] == "equal_weight_watchlist"
    assert summary["missing_data"]["partial_coverage"] is True
    assert any(item["missing_reason"] == "missing_price" for item in summary["missing_data"]["missing_inputs"])
    assert exposure["by_industry"]
    assert exposure["single_name_concentration"] == 0.5


def test_manual_weight_market_value_gain_loss_and_data_quality(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_symbol("600519", "白酒")
    _load_symbol("600000", "白酒")
    pid = _portfolio()
    repo = PortfolioRepository()
    repo.add_holding(pid, {"symbol": "600519", "quantity": 10, "cost_basis": 8, "weight_override": 0.7})
    repo.add_holding(pid, {"symbol": "600000", "quantity": 20, "cost_basis": 9, "weight_override": 0.3})
    with session_scope() as session:
        session.add(DataQualityIssue(issue_type="source_conflict", severity="medium", entity_type="company", entity_id="600519", symbol="600519", source_id="fixture", status="open", details={}))

    summary = PortfolioAnalyticsService().summary(pid)
    quality = PortfolioAnalyticsService().data_quality(pid)

    assert summary["market_value"] is not None
    assert summary["cost_value"] is not None
    assert summary["unrealized_gain_loss"] is not None
    assert summary["rows"][0]["weight_source"] == "manual_override"
    assert quality["portfolio_data_quality_score"] < 100
    assert quality["issues"]


def test_risk_performance_alerts_calendar_and_report(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_symbol("600519", "白酒")
    pid = _portfolio()
    repo = PortfolioRepository()
    repo.add_holding(pid, {"symbol": "600519", "quantity": 10, "cost_basis": 8})
    with session_scope() as session:
        session.add(Filing(symbol="600519", source_id="issuer", source_document_id="f1", title="annual", publication_date="2026-04-01"))
        session.add(
            ValuationRun(
                run_id="val_stage7",
                symbol="600519",
                as_of_date="2026-06-28",
                model_type="relative_valuation",
                scenario="base",
                assumption_hash="a",
                input_hash="i",
                result_json={"status": "calculated"},
                limitations_json=["limited_peer_count"],
            )
        )
        session.add(
            ReportRun(
                run_id="report_stage7",
                symbol="600519",
                as_of_date="2026-06-28",
                strict_as_of=False,
                bundle_hash="b",
                report_hash="r",
                status="completed",
                validation_status="failed",
                result_json={},
            )
        )
    risk = PortfolioRiskService().snapshot(pid)
    performance = PortfolioPerformanceService().performance(pid)
    rule = repo.add_alert_rule(pid, {"symbol": "600519", "rule_type": "price_above", "threshold": 10})
    evaluated = AlertsService().evaluate(pid)
    event = evaluated["triggered"][0]
    acknowledged = repo.set_alert_event_status(pid, int(event["event_id"]), "acknowledged")
    calendar_event = CalendarService().create_event({"portfolio_id": pid, "symbol": "600519", "title": "Review filing", "event_date": "2026-06-28"})
    report = PortfolioReportService().build(pid)

    assert rule["rule_type"] == "price_above"
    assert risk["weighted_volatility"] is not None
    assert risk["weighted_beta"]["missing_reason"] == "missing_benchmark"
    assert risk["valuation_risk_flags"]
    assert risk["report_validation_risk_flags"]
    assert performance["daily_value_series"]
    assert acknowledged and acknowledged["status"] == "acknowledged"
    assert calendar_event["source"] == "manual"
    assert CalendarService().list_events(portfolio_id=pid)["state"] == "available"
    assert report["validation"]["status"] == "passed"
    text = json.dumps({"risk": risk, "performance": performance, "event": event, "report": report}, ensure_ascii=False).lower()
    assert "target price" not in text
    assert "买入" not in text
    assert "卖出" not in text


def test_stage7_api_routes(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    _load_symbol("600519", "白酒")
    client = TestClient(app)

    created = client.post("/v1/portfolios", json={"name": "API Portfolio", "portfolio_type": "manual_holdings"})
    assert created.status_code == 200
    pid = created.json()["id"]
    assert client.get("/v1/portfolios").json()[0]["name"] == "API Portfolio"
    assert client.get(f"/v1/portfolios/{pid}").status_code == 200
    assert client.patch(f"/v1/portfolios/{pid}", json={"description": "local research"}).status_code == 200
    holding = client.post(f"/v1/portfolios/{pid}/holdings", json={"symbol": "600519", "quantity": 10, "cost_basis": 8})
    assert holding.status_code == 200
    holding_id = holding.json()["id"]
    assert client.patch(f"/v1/portfolios/{pid}/holdings/{holding_id}", json={"symbol": "600519", "quantity": 11}).status_code == 200
    watch = client.post(f"/v1/portfolios/{pid}/watch-items", json={"symbol": "000001", "thesis": "watch"}).json()
    assert client.patch(f"/v1/portfolios/{pid}/watch-items/{watch['id']}", json={"symbol": "000001", "interest_level": "low"}).status_code == 200
    assert client.get(f"/v1/portfolios/{pid}/summary").status_code == 200
    assert client.get(f"/v1/portfolios/{pid}/exposure").status_code == 200
    assert client.get(f"/v1/portfolios/{pid}/risk").status_code == 200
    assert client.get(f"/v1/portfolios/{pid}/performance").status_code == 200
    assert client.get(f"/v1/portfolios/{pid}/data-quality").status_code == 200
    assert client.get(f"/v1/portfolios/{pid}/report").status_code == 200
    rule = client.post(f"/v1/portfolios/{pid}/alerts/rules", json={"symbol": "600519", "rule_type": "price_above", "threshold": 10})
    assert rule.status_code == 200
    assert client.post(f"/v1/portfolios/{pid}/alerts/evaluate").status_code == 200
    events = client.get(f"/v1/portfolios/{pid}/alerts/events").json()
    assert events
    assert client.post(f"/v1/portfolios/{pid}/alerts/events/{events[0]['event_id']}/dismiss").status_code == 200
    calendar = client.post("/v1/calendar/events", json={"portfolio_id": pid, "symbol": "600519", "title": "Manual review", "event_date": "2026-06-28"})
    assert calendar.status_code == 200
    assert client.get(f"/v1/calendar/events?portfolio_id={pid}").json()["state"] == "available"
    assert client.delete(f"/v1/portfolios/{pid}/watch-items/{watch['id']}").status_code == 200
    assert client.delete(f"/v1/portfolios/{pid}/holdings/{holding_id}").status_code == 200
    assert client.delete(f"/v1/portfolios/{pid}").status_code == 200
