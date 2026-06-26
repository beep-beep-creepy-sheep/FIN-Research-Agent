"""professional metric metadata

Revision ID: 0003_metric_metadata
Revises: 0002_stage2_metadata_fields
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Boolean, Column, Integer, JSON, String, Text, inspect


revision = "0003_metric_metadata"
down_revision = "0002_stage2_metadata_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    _add_if_missing(
        bind,
        "metric_definitions",
        Column("implementation_status", String(64), nullable=False, server_default="defined_only"),
    )
    _add_if_missing(bind, "metric_definitions", Column("calculation_domain", String(64)))
    _add_if_missing(bind, "metric_definitions", Column("minimum_inputs", JSON))
    _add_if_missing(bind, "metric_definitions", Column("period_requirements", Text))
    _add_if_missing(
        bind,
        "metric_definitions",
        Column("benchmark_required", Boolean, nullable=False, server_default="false"),
    )
    _add_if_missing(
        bind,
        "metric_definitions",
        Column("market_data_required", Boolean, nullable=False, server_default="false"),
    )

    _add_if_missing(bind, "metric_observations", Column("period_start", String(32)))
    _add_if_missing(bind, "metric_observations", Column("source_urls", JSON))
    _add_if_missing(bind, "metric_observations", Column("price_source", String(128)))
    _add_if_missing(bind, "metric_observations", Column("benchmark_code", String(64)))
    _add_if_missing(bind, "metric_observations", Column("benchmark_source", String(128)))
    _add_if_missing(bind, "metric_observations", Column("start_date", String(32)))
    _add_if_missing(bind, "metric_observations", Column("end_date", String(32)))
    _add_if_missing(bind, "metric_observations", Column("observations_count", Integer))
    _add_if_missing(bind, "metric_observations", Column("adjustment_type", String(32)))
    _add_if_missing(bind, "metric_observations", Column("assumptions", JSON))


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, column_name in [
        ("metric_observations", "assumptions"),
        ("metric_observations", "adjustment_type"),
        ("metric_observations", "observations_count"),
        ("metric_observations", "end_date"),
        ("metric_observations", "start_date"),
        ("metric_observations", "benchmark_source"),
        ("metric_observations", "benchmark_code"),
        ("metric_observations", "price_source"),
        ("metric_observations", "source_urls"),
        ("metric_observations", "period_start"),
        ("metric_definitions", "market_data_required"),
        ("metric_definitions", "benchmark_required"),
        ("metric_definitions", "period_requirements"),
        ("metric_definitions", "minimum_inputs"),
        ("metric_definitions", "calculation_domain"),
        ("metric_definitions", "implementation_status"),
    ]:
        _drop_column_if_exists(bind, table_name, column_name)


def _add_if_missing(bind, table_name: str, column: Column) -> None:
    columns = {row["name"] for row in inspect(bind).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def _drop_column_if_exists(bind, table_name: str, column_name: str) -> None:
    columns = {row["name"] for row in inspect(bind).get_columns(table_name)}
    if column_name in columns:
        op.drop_column(table_name, column_name)
