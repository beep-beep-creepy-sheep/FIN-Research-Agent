from app.models import CompanyRecord, PriceRecord
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.job_service import JobService
from finresearch.services.market_snapshot import MarketSnapshotService


def _set_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'snapshot.sqlite'}")


def test_market_snapshot_returns_insufficient_data_without_prices(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)

    result = MarketSnapshotService().generate("CN")

    assert result.snapshot["status"] == "insufficient_data"
    assert result.snapshot["summary"]["universe_count"] == 0
    assert result.breadth is None
    assert result.warnings == ["missing_local_price_data"]


def test_market_snapshot_builds_breadth_sectors_and_movers(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    company_repo = CompanyRepository()
    price_repo = PriceRepository()
    company_repo.upsert(CompanyRecord(symbol="600519", company_name="贵州茅台", exchange="SSE", industry="白酒"))
    company_repo.upsert(CompanyRecord(symbol="000001", company_name="平安银行", exchange="SZSE", industry="银行"))
    price_repo.upsert_many(
        [
            PriceRecord(
                symbol="600519",
                trade_date="2026-06-25",
                close=100.0,
                amount=1000.0,
                adjustment_type="qfq",
                data_source="fixture",
                retrieved_at="2026-06-25T00:00:00+00:00",
            ),
            PriceRecord(
                symbol="600519",
                trade_date="2026-06-26",
                close=110.0,
                amount=1500.0,
                adjustment_type="qfq",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
            PriceRecord(
                symbol="000001",
                trade_date="2026-06-25",
                close=10.0,
                amount=900.0,
                adjustment_type="qfq",
                data_source="fixture",
                retrieved_at="2026-06-25T00:00:00+00:00",
            ),
            PriceRecord(
                symbol="000001",
                trade_date="2026-06-26",
                close=9.0,
                amount=800.0,
                adjustment_type="qfq",
                data_source="fixture",
                retrieved_at="2026-06-26T00:00:00+00:00",
            ),
        ]
    )

    result = MarketSnapshotService().generate("CN")

    assert result.snapshot["status"] == "draft"
    assert result.breadth["advance_count"] == 1
    assert result.breadth["decline_count"] == 1
    assert {sector["sector_name"] for sector in result.sectors} == {"白酒", "银行"}
    assert result.movers["gainers"][0]["symbol"] == "600519"
    assert result.movers["losers"][0]["symbol"] == "000001"


def test_market_snapshot_job_runs_through_database_worker(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    service = JobService(tmp_path)

    job = service.create_market_snapshot_job("CN")
    result = service.run_next()

    assert job["status"] == "queued"
    assert result["status"] == "completed"
    assert result["result"]["snapshot"]["status"] == "insufficient_data"
