from sqlalchemy import inspect

from finresearch.database.session import build_engine, database_url, init_db
from finresearch.repositories.market import MarketRepository, MetricDefinitionRepository


def _set_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'market.sqlite'}")


def test_market_tables_are_created(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    init_db()

    tables = set(inspect(build_engine(database_url())).get_table_names())

    assert "metric_definitions" in tables
    assert "metric_observations" in tables
    assert "market_snapshots" in tables
    assert "security_quotes" in tables
    assert "market_breadth_snapshots" in tables
    assert "screen_definitions" in tables


def test_metric_definition_repository_syncs_registry(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    repo = MetricDefinitionRepository()

    count = repo.sync_registry()
    rows = repo.list()

    assert count >= 35
    assert len(rows) == count
    assert {row["code"] for row in rows} >= {"net_margin", "roe", "pe"}


def test_market_repository_upserts_snapshot_and_quotes(monkeypatch, tmp_path) -> None:
    _set_database(monkeypatch, tmp_path)
    repo = MarketRepository()

    snapshot = repo.upsert_snapshot(
        market="CN",
        snapshot_date="2026-06-26",
        as_of="2026-06-26T01:00:00+00:00",
        status="draft",
        headline="本地行情覆盖不足",
        summary={"universe_count": 1},
        coverage={"prices": 1},
        data_quality={"warnings": ["limited_universe"]},
        source_count=1,
    )
    repo.upsert_security_quotes(
        [
            {
                "symbol": "600519",
                "name": "贵州茅台",
                "market": "CN",
                "sector": "consumer",
                "trade_date": "2026-06-26",
                "close": 1500.0,
                "prev_close": 1490.0,
                "change_pct": 0.0067,
                "amount": 1000000.0,
                "data_source": "fixture",
                "retrieved_at": "2026-06-26T01:00:00+00:00",
            }
        ]
    )
    repo.upsert_breadth(
        {
            "market": "CN",
            "trade_date": "2026-06-26",
            "universe_count": 1,
            "advance_count": 1,
            "decline_count": 0,
            "flat_count": 0,
            "data_source": "fixture",
            "retrieved_at": "2026-06-26T01:00:00+00:00",
        }
    )

    assert snapshot["headline"] == "本地行情覆盖不足"
    assert repo.latest_snapshot("CN")["summary"]["universe_count"] == 1
    assert repo.list_security_quotes(market="CN")[0]["symbol"] == "600519"
    assert repo.latest_breadth("CN")["advance_count"] == 1
