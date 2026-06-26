"""stage 2 metadata fields

Revision ID: 0002_stage2_metadata_fields
Revises: 0001_initial_schema
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Boolean, Column, JSON, String, Text, inspect


revision = "0002_stage2_metadata_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    _add_if_missing(bind, "metric_definitions", Column("applicable_industries", JSON))
    _add_if_missing(bind, "metric_definitions", Column("caveats", Text))
    _add_if_missing(
        bind,
        "metric_definitions",
        Column("calculation_version", String(64), nullable=False, server_default="1.0.0"),
    )
    _add_if_missing(bind, "metric_observations", Column("as_of", String(64)))
    _add_if_missing(bind, "metric_observations", Column("formula_version", String(64)))
    _add_if_missing(bind, "metric_observations", Column("warnings", JSON))
    _add_if_missing(bind, "market_snapshots", Column("observed_at", String(64)))
    _add_if_missing(bind, "market_snapshots", Column("fetched_at", String(64)))
    _add_if_missing(bind, "market_snapshots", Column("trading_date", String(32)))
    _add_if_missing(bind, "market_snapshots", Column("currency", String(16)))
    _add_if_missing(bind, "market_snapshots", Column("unit", String(64)))
    _add_if_missing(
        bind,
        "market_snapshots",
        Column("quality_status", String(64), server_default="draft"),
    )
    _add_if_missing(
        bind,
        "market_snapshots",
        Column("is_stale", Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    pass


def _add_if_missing(bind, table_name: str, column: Column) -> None:
    columns = {row["name"] for row in inspect(bind).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)
