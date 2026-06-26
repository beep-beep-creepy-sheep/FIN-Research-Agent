from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import inspect

from finresearch.database.session import build_engine, database_url, init_db


def test_init_db_is_safe_to_call_concurrently(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'concurrent.sqlite'}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _index: init_db(), range(8)))

    tables = set(inspect(build_engine(database_url())).get_table_names())

    assert "companies" in tables
    assert "metric_definitions" in tables
