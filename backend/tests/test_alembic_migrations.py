from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head_on_empty_sqlite(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "empty.sqlite"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_path}")
    config = Config("alembic.ini")

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    tables = set(inspect(create_engine(f"sqlite:///{db_path}")).get_table_names())
    assert "companies" in tables
    assert "market_snapshots" in tables
    assert "alembic_version" in tables
