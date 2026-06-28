"""stage 7 portfolio risk alerts calendar

Revision ID: 0007_stage7_portfolio
Revises: 0006_stage6_reports
Create Date: 2026-06-28
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, inspect


revision = "0007_stage7_portfolio"
down_revision = "0006_stage6_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("portfolios"):
        op.create_table(
            "portfolios",
            Column("id", Integer, primary_key=True),
            Column("name", String(255), nullable=False),
            Column("description", Text),
            Column("base_currency", String(16), nullable=False, server_default="CNY"),
            Column("portfolio_type", String(64), nullable=False, server_default="watchlist"),
            Column("archived", Boolean, nullable=False, server_default="0"),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
    if not inspect(bind).has_table("portfolio_holdings"):
        op.create_table(
            "portfolio_holdings",
            Column("id", Integer, primary_key=True),
            Column("portfolio_id", Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
            Column("symbol", String(32), nullable=False),
            Column("quantity", Float),
            Column("cost_basis", Float),
            Column("cost_currency", String(16)),
            Column("position_date", String(32)),
            Column("weight_override", Float),
            Column("notes", Text),
            Column("source", String(64), nullable=False, server_default="manual"),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )
    if not inspect(bind).has_table("portfolio_watch_items"):
        op.create_table(
            "portfolio_watch_items",
            Column("id", Integer, primary_key=True),
            Column("portfolio_id", Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
            Column("symbol", String(32), nullable=False),
            Column("thesis", Text),
            Column("interest_level", String(64)),
            Column("tags", JSON),
            Column("added_at", DateTime),
            Column("notes", Text),
        )
    if not inspect(bind).has_table("portfolio_snapshots"):
        op.create_table(
            "portfolio_snapshots",
            Column("id", Integer, primary_key=True),
            Column("portfolio_id", Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
            Column("snapshot_date", String(32), nullable=False),
            Column("summary_json", JSON, nullable=False),
            Column("created_at", DateTime),
        )
    if not inspect(bind).has_table("portfolio_risk_runs"):
        op.create_table(
            "portfolio_risk_runs",
            Column("id", Integer, primary_key=True),
            Column("run_id", String(128), nullable=False),
            Column("portfolio_id", Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
            Column("as_of_date", String(32), nullable=False),
            Column("result_json", JSON, nullable=False),
            Column("created_at", DateTime),
        )
    if not inspect(bind).has_table("portfolio_alert_rules"):
        op.create_table(
            "portfolio_alert_rules",
            Column("id", Integer, primary_key=True),
            Column("portfolio_id", Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
            Column("symbol", String(32)),
            Column("rule_type", String(64), nullable=False),
            Column("metric_code", String(128)),
            Column("threshold", Float),
            Column("direction", String(32)),
            Column("enabled", Boolean, nullable=False, server_default="1"),
            Column("severity", String(64), nullable=False, server_default="medium"),
            Column("last_evaluated_at", String(64)),
            Column("last_triggered_at", String(64)),
            Column("created_at", DateTime),
        )
    if not inspect(bind).has_table("portfolio_alert_events"):
        op.create_table(
            "portfolio_alert_events",
            Column("id", Integer, primary_key=True),
            Column("rule_id", Integer, ForeignKey("portfolio_alert_rules.id", ondelete="SET NULL")),
            Column("portfolio_id", Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
            Column("symbol", String(32)),
            Column("triggered_at", String(64), nullable=False),
            Column("message", Text, nullable=False),
            Column("evidence_json", JSON),
            Column("status", String(64), nullable=False, server_default="new"),
            Column("severity", String(64), nullable=False, server_default="medium"),
        )
    if not inspect(bind).has_table("portfolio_calendar_events"):
        op.create_table(
            "portfolio_calendar_events",
            Column("id", Integer, primary_key=True),
            Column("portfolio_id", Integer, ForeignKey("portfolios.id", ondelete="CASCADE")),
            Column("symbol", String(32)),
            Column("event_type", String(64), nullable=False),
            Column("title", String(500), nullable=False),
            Column("event_date", String(32), nullable=False),
            Column("source", String(128), nullable=False, server_default="manual"),
            Column("filing_id", Integer, ForeignKey("filings.id", ondelete="SET NULL")),
            Column("report_run_id", Integer, ForeignKey("report_runs.id", ondelete="SET NULL")),
            Column("notes", Text),
            Column("severity", String(64), nullable=False, server_default="medium"),
            Column("created_at", DateTime),
        )
    for table_name, index_name, columns in [
        ("portfolios", "ix_portfolios_name", ["name"]),
        ("portfolios", "ix_portfolios_archived", ["archived"]),
        ("portfolio_holdings", "ix_portfolio_holdings_portfolio_id", ["portfolio_id"]),
        ("portfolio_holdings", "ix_portfolio_holdings_symbol", ["symbol"]),
        ("portfolio_watch_items", "ix_portfolio_watch_items_portfolio_id", ["portfolio_id"]),
        ("portfolio_watch_items", "ix_portfolio_watch_items_symbol", ["symbol"]),
        ("portfolio_snapshots", "ix_portfolio_snapshots_portfolio_id", ["portfolio_id"]),
        ("portfolio_snapshots", "ix_portfolio_snapshots_snapshot_date", ["snapshot_date"]),
        ("portfolio_risk_runs", "ix_portfolio_risk_runs_run_id", ["run_id"]),
        ("portfolio_risk_runs", "ix_portfolio_risk_runs_portfolio_id", ["portfolio_id"]),
        ("portfolio_risk_runs", "ix_portfolio_risk_runs_as_of_date", ["as_of_date"]),
        ("portfolio_alert_rules", "ix_portfolio_alert_rules_portfolio_id", ["portfolio_id"]),
        ("portfolio_alert_rules", "ix_portfolio_alert_rules_symbol", ["symbol"]),
        ("portfolio_alert_rules", "ix_portfolio_alert_rules_rule_type", ["rule_type"]),
        ("portfolio_alert_events", "ix_portfolio_alert_events_rule_id", ["rule_id"]),
        ("portfolio_alert_events", "ix_portfolio_alert_events_portfolio_id", ["portfolio_id"]),
        ("portfolio_alert_events", "ix_portfolio_alert_events_symbol", ["symbol"]),
        ("portfolio_alert_events", "ix_portfolio_alert_events_triggered_at", ["triggered_at"]),
        ("portfolio_alert_events", "ix_portfolio_alert_events_status", ["status"]),
        ("portfolio_calendar_events", "ix_portfolio_calendar_events_portfolio_id", ["portfolio_id"]),
        ("portfolio_calendar_events", "ix_portfolio_calendar_events_symbol", ["symbol"]),
        ("portfolio_calendar_events", "ix_portfolio_calendar_events_event_type", ["event_type"]),
        ("portfolio_calendar_events", "ix_portfolio_calendar_events_event_date", ["event_date"]),
    ]:
        _create_index_if_missing(bind, table_name, index_name, columns)
    for table_name, name, columns in [
        ("portfolios", "uq_portfolio_name", ["name"]),
        ("portfolio_holdings", "uq_portfolio_holding_symbol", ["portfolio_id", "symbol"]),
        ("portfolio_watch_items", "uq_portfolio_watch_symbol", ["portfolio_id", "symbol"]),
        ("portfolio_risk_runs", "uq_portfolio_risk_run_id", ["run_id"]),
    ]:
        _create_unique_if_missing(bind, table_name, name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in (
        "portfolio_calendar_events",
        "portfolio_alert_events",
        "portfolio_alert_rules",
        "portfolio_risk_runs",
        "portfolio_snapshots",
        "portfolio_watch_items",
        "portfolio_holdings",
        "portfolios",
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
