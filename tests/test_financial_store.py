from pathlib import Path

from app.database import connect, migrate
from app.financial_store import FinancialStore
from app.models import CompanyRecord, FinancialFact, PriceRecord


def _fact(symbol: str = "600519", period_end: str = "2024-12-31", publication_date: str = "2025-04-01") -> FinancialFact:
    return FinancialFact(
        symbol=symbol,
        metric_code="revenue",
        metric_name="营业收入",
        value=100.0,
        unit="元",
        currency="CNY",
        period_end=period_end,
        publication_date=publication_date,
        report_type="annual",
        statement_type="profit_sheet",
        data_source="test",
        retrieved_at="2026-01-01T00:00:00+00:00",
    )


def test_migrations_create_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "library.sqlite"
    migrate(db_path)

    with connect(db_path) as db:
        tables = {
            row["name"]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
        }

    assert "companies" in tables
    assert "financial_facts" in tables
    assert "prices" in tables
    assert "sync_errors" in tables


def test_financial_fact_upsert_is_idempotent(tmp_path: Path) -> None:
    store = FinancialStore(tmp_path / "library.sqlite")
    store.upsert_company(CompanyRecord(symbol="600519", company_name="贵州茅台"))

    assert store.upsert_facts([_fact()]) == 1
    assert store.upsert_facts([_fact()]) == 1
    rows = store.facts("600519")

    assert len(rows) == 1
    assert rows[0]["value"] == 100.0


def test_as_of_filter_excludes_future_publications(tmp_path: Path) -> None:
    store = FinancialStore(tmp_path / "library.sqlite")
    store.upsert_facts(
        [
            _fact(period_end="2023-12-31", publication_date="2024-04-01"),
            _fact(period_end="2024-12-31", publication_date="2025-04-01"),
        ]
    )

    rows = store.facts("600519", as_of_date="2024-12-31")

    assert len(rows) == 1
    assert rows[0]["period_end"] == "2023-12-31"


def test_price_upsert_is_idempotent(tmp_path: Path) -> None:
    store = FinancialStore(tmp_path / "library.sqlite")
    price = PriceRecord(
        symbol="600519",
        trade_date="2024-01-02",
        close=100.0,
        adjustment_type="qfq",
        data_source="test",
        retrieved_at="2026-01-01T00:00:00+00:00",
    )

    store.upsert_prices([price])
    store.upsert_prices([price.model_copy(update={"close": 101.0})])
    company = store.get_company("600519")

    assert company is None
    with connect(tmp_path / "library.sqlite") as db:
        row = db.execute("SELECT close FROM prices WHERE symbol = ?", ("600519",)).fetchone()
    assert row["close"] == 101.0
