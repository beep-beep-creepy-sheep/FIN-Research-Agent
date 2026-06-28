"""stage 5 peers screener valuation

Revision ID: 0005_stage5_peers
Revises: 0004_stage3_sources
Create Date: 2026-06-28
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, inspect


revision = "0005_stage5_peers"
down_revision = "0004_stage3_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("peer_sets"):
        op.create_table(
            "peer_sets",
            Column("id", Integer, primary_key=True),
            Column("symbol", String(32), nullable=False),
            Column("as_of_date", String(32), nullable=False),
            Column("peer_set_hash", String(128), nullable=False),
            Column("selection_method", String(64), nullable=False, server_default="auto"),
            Column("quality_flags", JSON),
            Column("limitations", JSON),
            Column("version", String(64), nullable=False, server_default="stage5-peer-v1"),
            Column("created_at", DateTime),
        )
    if not inspect(bind).has_table("peer_set_members"):
        op.create_table(
            "peer_set_members",
            Column("id", Integer, primary_key=True),
            Column("peer_set_id", Integer, ForeignKey("peer_sets.id", ondelete="CASCADE"), nullable=False),
            Column("symbol", String(32), nullable=False),
            Column("name", String(255)),
            Column("exchange", String(32)),
            Column("industry", String(255)),
            Column("sector", String(255)),
            Column("market_cap", Float),
            Column("revenue", Float),
            Column("selected", Boolean, nullable=False, server_default="1"),
            Column("reason", Text),
            Column("similarity_score", Float),
            Column("source", String(64), nullable=False, server_default="auto"),
            Column("limitations", JSON),
        )
    if not inspect(bind).has_table("valuation_runs"):
        op.create_table(
            "valuation_runs",
            Column("id", Integer, primary_key=True),
            Column("run_id", String(128), nullable=False),
            Column("symbol", String(32), nullable=False),
            Column("as_of_date", String(32), nullable=False),
            Column("model_type", String(64), nullable=False),
            Column("scenario", String(64), nullable=False),
            Column("assumption_hash", String(128), nullable=False),
            Column("input_hash", String(128), nullable=False),
            Column("result_json", JSON, nullable=False),
            Column("evidence_json", JSON),
            Column("limitations_json", JSON),
            Column("valuation_version", String(64), nullable=False, server_default="stage5-valuation-v1"),
            Column("created_at", DateTime),
        )
    if not inspect(bind).has_table("valuation_assumptions"):
        op.create_table(
            "valuation_assumptions",
            Column("id", Integer, primary_key=True),
            Column("assumption_set_id", String(128), nullable=False),
            Column("symbol", String(32), nullable=False),
            Column("model_type", String(64), nullable=False),
            Column("scenario", String(64), nullable=False),
            Column("assumptions_json", JSON, nullable=False),
            Column("created_by", String(64), nullable=False, server_default="system"),
            Column("source", String(64), nullable=False, server_default="default"),
            Column("version", String(64), nullable=False, server_default="stage5-assumptions-v1"),
            Column("created_at", DateTime),
        )
    if not inspect(bind).has_table("screen_presets"):
        op.create_table(
            "screen_presets",
            Column("id", Integer, primary_key=True),
            Column("name", String(255), nullable=False),
            Column("filters_json", JSON, nullable=False),
            Column("created_by", String(64), nullable=False, server_default="local_user"),
            Column("created_at", DateTime),
        )
    for table_name, index_name, columns in [
        ("peer_sets", "ix_peer_sets_symbol", ["symbol"]),
        ("peer_sets", "ix_peer_sets_as_of_date", ["as_of_date"]),
        ("peer_sets", "ix_peer_sets_peer_set_hash", ["peer_set_hash"]),
        ("peer_set_members", "ix_peer_set_members_peer_set_id", ["peer_set_id"]),
        ("peer_set_members", "ix_peer_set_members_symbol", ["symbol"]),
        ("valuation_runs", "ix_valuation_runs_run_id", ["run_id"]),
        ("valuation_runs", "ix_valuation_runs_symbol", ["symbol"]),
        ("valuation_runs", "ix_valuation_runs_as_of_date", ["as_of_date"]),
        ("valuation_runs", "ix_valuation_runs_model_type", ["model_type"]),
        ("valuation_runs", "ix_valuation_runs_scenario", ["scenario"]),
        ("valuation_runs", "ix_valuation_runs_assumption_hash", ["assumption_hash"]),
        ("valuation_runs", "ix_valuation_runs_input_hash", ["input_hash"]),
        ("valuation_assumptions", "ix_valuation_assumptions_assumption_set_id", ["assumption_set_id"]),
        ("valuation_assumptions", "ix_valuation_assumptions_symbol", ["symbol"]),
        ("valuation_assumptions", "ix_valuation_assumptions_model_type", ["model_type"]),
        ("valuation_assumptions", "ix_valuation_assumptions_scenario", ["scenario"]),
        ("screen_presets", "ix_screen_presets_name", ["name"]),
    ]:
        _create_index_if_missing(bind, table_name, index_name, columns)
    for table_name, name, columns in [
        ("peer_sets", "uq_peer_set_hash", ["symbol", "as_of_date", "peer_set_hash"]),
        ("peer_set_members", "uq_peer_set_member", ["peer_set_id", "symbol"]),
        ("valuation_runs", "uq_valuation_run_id", ["run_id"]),
        ("screen_presets", "uq_screen_preset_name", ["name"]),
    ]:
        _create_unique_if_missing(bind, table_name, name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in (
        "screen_presets",
        "valuation_assumptions",
        "valuation_runs",
        "peer_set_members",
        "peer_sets",
    ):
        if inspect(bind).has_table(table_name):
            op.drop_table(table_name)


def _create_index_if_missing(bind, table_name: str, index_name: str, columns: list[str]) -> None:
    indexes = {row["name"] for row in inspect(bind).get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def _create_unique_if_missing(bind, table_name: str, constraint_name: str, columns: list[str]) -> None:
    constraints = {row["name"] for row in inspect(bind).get_unique_constraints(table_name)}
    if constraint_name in constraints:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(constraint_name, columns)
    else:
        op.create_unique_constraint(constraint_name, table_name, columns)
