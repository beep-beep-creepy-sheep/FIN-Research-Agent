from app.models import CompanyRecord, FinancialFact, PriceRecord
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.jobs import JobRepository
from finresearch.repositories.prices import PriceRepository


def _set_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'repo.sqlite'}")


def test_sqlalchemy_company_fact_price_repositories(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    company_repo = CompanyRepository()
    fact_repo = FinancialFactRepository()
    price_repo = PriceRepository()

    company_repo.upsert(CompanyRecord(symbol="600519", company_name="贵州茅台", exchange="SSE"))
    fact_repo.upsert_many(
        [
            FinancialFact(
                symbol="600519",
                metric_code="revenue",
                metric_name="营业收入",
                value=100.0,
                period_end="2024-12-31",
                publication_date="2025-04-01",
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-01-01T00:00:00+00:00",
            )
        ]
    )
    price_repo.upsert_many(
        [
            PriceRecord(
                symbol="600519",
                trade_date="2025-01-02",
                close=88.0,
                adjustment_type="qfq",
                data_source="fixture",
                retrieved_at="2026-01-01T00:00:00+00:00",
            )
        ]
    )

    assert company_repo.get("600519")["facts_count"] == 1
    assert fact_repo.matrix("600519")[0]["revenue"] == 100.0
    assert price_repo.list_by_symbol("600519")[0]["close"] == 88.0


def test_strict_as_of_excludes_unknown_publication_date(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    fact_repo = FinancialFactRepository()
    fact_repo.upsert_many(
        [
            FinancialFact(
                symbol="600519",
                metric_code="revenue",
                metric_name="营业收入",
                value=100.0,
                period_end="2024-12-31",
                publication_date=None,
                report_type="annual",
                statement_type="profit_sheet",
                data_source="fixture",
                retrieved_at="2026-01-01T00:00:00+00:00",
            )
        ]
    )

    loose = fact_repo.list_by_symbol("600519", as_of_date="2025-01-01")
    strict = fact_repo.list_by_symbol("600519", as_of_date="2025-01-01", strict_as_of=True)

    assert len(loose) == 1
    assert strict == []


def test_sqlalchemy_job_repository(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    repo = JobRepository()

    created = repo.create("sync_company", {"symbol": "600519", "years": 5})
    repo.update(int(created["id"]), status="running", progress=50, current_stage="fetching")
    updated = repo.get(int(created["id"]))

    assert updated["status"] == "running"
    assert updated["payload"]["symbol"] == "600519"
