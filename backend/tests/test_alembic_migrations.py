from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from finresearch.database.models import Base


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


def test_alembic_head_schema_matches_model_metadata(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "schema.sqlite"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_path}")
    config = Config("alembic.ini")

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{db_path}"))
    actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
    expected_tables = set(Base.metadata.tables)
    assert actual_tables == expected_tables

    for table_name, table in Base.metadata.tables.items():
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        expected_columns = {column.name for column in table.columns}
        assert actual_columns == expected_columns, table_name

        actual_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        expected_indexes = {index.name for index in table.indexes}
        assert actual_indexes == expected_indexes, table_name

        actual_unique = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints(table_name)
            if constraint["name"]
        }
        expected_unique = {
            constraint.name
            for constraint in table.constraints
            if constraint.name and constraint.__class__.__name__ == "UniqueConstraint"
        }
        assert expected_unique.issubset(actual_unique), table_name
