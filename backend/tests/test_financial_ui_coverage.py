from app.models import CompanyRecord, FinancialFact, PriceRecord
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.company_charts import CompanyChartService
from finresearch.services.screener import ScreenQuery, ScreenerService


def _set_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'coverage.sqlite'}")


def _seed_company() -> None:
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
                value=25.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
            FinancialFact(
                symbol="600519",
                metric_code="operating_cash_flow",
                metric_name="经营现金流",
                value=30.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="cash_flow",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
            FinancialFact(
                symbol="600519",
                metric_code="total_assets",
                metric_name="总资产",
                value=200.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="balance_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
            FinancialFact(
                symbol="600519",
                metric_code="total_equity",
                metric_name="所有者权益",
                value=120.0,
                period_end="2025-12-31",
                report_type="annual",
                statement_type="balance_sheet",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
        ]
    )
    PriceRepository().upsert_many(
        [
            PriceRecord(
                symbol="600519",
                trade_date="2026-06-26",
                open=100.0,
                high=110.0,
                low=99.0,
                close=108.0,
                volume=1000.0,
                amount=108000.0,
                adjustment_type="qfq",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            )
        ]
    )


def test_company_chart_suite_uses_local_facts_and_prices(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    _seed_company()

    charts = {chart["id"]: chart for chart in CompanyChartService(tmp_path).build("600519")}

    assert charts["kline_volume"]["empty"] is False
    assert charts["financial_trend"]["data"][0]["revenue"] == 100.0
    assert charts["margin_trend"]["data"][0]["net_margin"] == 0.25
    assert charts["returns_trend"]["data"][0]["roe"] == 25.0 / 120.0
    assert charts["valuation_band"]["empty"] is True


def test_screener_filters_on_database_calculated_ratios(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    _seed_company()

    passing = ScreenerService().query(ScreenQuery(min_net_margin=0.2, min_roe=0.1))
    failing = ScreenerService().query(ScreenQuery(min_net_margin=0.4))

    assert passing["count"] == 1
    assert passing["rows"][0]["symbol"] == "600519"
    assert failing["count"] == 0
