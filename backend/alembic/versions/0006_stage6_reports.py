"""stage 6 institutional reports

Revision ID: 0006_stage6_reports
Revises: 0005_stage5_peers
Create Date: 2026-06-28
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, inspect


revision = "0006_stage6_reports"
down_revision = "0005_stage5_peers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("report_runs"):
        op.create_table(
            "report_runs",
            Column("id", Integer, primary_key=True),
            Column("run_id", String(128), nullable=False),
            Column("symbol", String(32), nullable=False),
            Column("as_of_date", String(32), nullable=False),
            Column("strict_as_of", Boolean, nullable=False, server_default="0"),
            Column("report_style", String(64), nullable=False, server_default="institutional_full"),
            Column("language", String(16), nullable=False, server_default="en"),
            Column("bundle_hash", String(128), nullable=False),
            Column("report_hash", String(128), nullable=False),
            Column("report_version", String(64), nullable=False, server_default="stage6-report-v1"),
            Column("status", String(64), nullable=False, server_default="completed"),
            Column("llm_enabled", Boolean, nullable=False, server_default="0"),
            Column("llm_provider", String(64)),
            Column("model_name", String(128)),
            Column("validation_status", String(64), nullable=False, server_default="passed"),
            Column("result_json", JSON, nullable=False),
            Column("markdown", Text),
            Column("html", Text),
            Column("validation_json", JSON),
            Column("evidence_json", JSON),
            Column("limitations_json", JSON),
            Column("created_at", DateTime),
        )
    if not inspect(bind).has_table("report_sections"):
        op.create_table(
            "report_sections",
            Column("id", Integer, primary_key=True),
            Column("report_run_id", Integer, ForeignKey("report_runs.id", ondelete="CASCADE"), nullable=False),
            Column("section_id", String(128), nullable=False),
            Column("title", String(255), nullable=False),
            Column("status", String(64), nullable=False, server_default="completed"),
            Column("generated_by", String(64), nullable=False, server_default="deterministic_python"),
            Column("validation_status", String(64), nullable=False, server_default="passed"),
            Column("content_json", JSON, nullable=False),
            Column("evidence_ids_json", JSON),
            Column("limitations_json", JSON),
        )
    if not inspect(bind).has_table("ai_prompt_audits"):
        op.create_table(
            "ai_prompt_audits",
            Column("id", Integer, primary_key=True),
            Column("report_run_id", Integer, ForeignKey("report_runs.id", ondelete="CASCADE")),
            Column("section_id", String(128)),
            Column("prompt_hash", String(128), nullable=False),
            Column("response_hash", String(128)),
            Column("provider", String(64)),
            Column("model_name", String(128)),
            Column("validation_status", String(64), nullable=False, server_default="not_used"),
            Column("unsupported_claims_json", JSON),
            Column("created_at", DateTime),
        )
    for table_name, index_name, columns in [
        ("report_runs", "ix_report_runs_run_id", ["run_id"]),
        ("report_runs", "ix_report_runs_symbol", ["symbol"]),
        ("report_runs", "ix_report_runs_as_of_date", ["as_of_date"]),
        ("report_runs", "ix_report_runs_bundle_hash", ["bundle_hash"]),
        ("report_runs", "ix_report_runs_report_hash", ["report_hash"]),
        ("report_runs", "ix_report_runs_status", ["status"]),
        ("report_runs", "ix_report_runs_validation_status", ["validation_status"]),
        ("report_sections", "ix_report_sections_report_run_id", ["report_run_id"]),
        ("report_sections", "ix_report_sections_section_id", ["section_id"]),
        ("ai_prompt_audits", "ix_ai_prompt_audits_report_run_id", ["report_run_id"]),
        ("ai_prompt_audits", "ix_ai_prompt_audits_section_id", ["section_id"]),
        ("ai_prompt_audits", "ix_ai_prompt_audits_prompt_hash", ["prompt_hash"]),
    ]:
        _create_index_if_missing(bind, table_name, index_name, columns)
    for table_name, name, columns in [
        ("report_runs", "uq_report_run_id", ["run_id"]),
        ("report_sections", "uq_report_section", ["report_run_id", "section_id"]),
    ]:
        _create_unique_if_missing(bind, table_name, name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("ai_prompt_audits", "report_sections", "report_runs"):
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
