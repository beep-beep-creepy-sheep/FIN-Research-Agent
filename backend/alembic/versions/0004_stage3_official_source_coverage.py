"""stage 3 official source coverage

Revision ID: 0004_stage3_sources
Revises: 0003_metric_metadata
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, inspect


revision = "0004_stage3_sources"
down_revision = "0003_metric_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    for column in [
        Column("symbol", String(32)),
        Column("exchange", String(32)),
        Column("source_id", String(128)),
        Column("source_document_id", String(255)),
        Column("document_type", String(64)),
        Column("announcement_category", String(128)),
        Column("period_start", String(32)),
        Column("period_end", String(32)),
        Column("published_at", String(64)),
        Column("canonical_url", Text),
        Column("download_url", Text),
        Column("original_filename", String(255)),
        Column("language", String(32)),
        Column("content_type", String(128)),
        Column("content_length", Integer),
        Column("sha256", String(128)),
        Column("etag", String(255)),
        Column("last_modified", String(128)),
        Column("raw_metadata_path", Text),
        Column("verification_status", String(64), server_default="unverified"),
        Column("source_tier", String(64), server_default="unknown"),
        Column("retrieved_at", String(64)),
        Column("last_attempt_at", String(64)),
        Column("retry_count", Integer, server_default="0"),
        Column("error_type", String(128)),
        Column("error_message", Text),
        Column("updated_at", DateTime),
    ]:
        _add_if_missing(bind, "filings", column)

    _create_index_if_missing(bind, "filings", "ix_filings_symbol", ["symbol"])
    _create_index_if_missing(bind, "filings", "ix_filings_source_id", ["source_id"])
    _create_index_if_missing(
        bind, "filings", "ix_filings_source_document_id", ["source_document_id"]
    )
    _create_index_if_missing(bind, "filings", "ix_filings_sha256", ["sha256"])
    _create_unique_if_missing(
        bind, "filings", "uq_filing_source_document", ["source_id", "source_document_id"]
    )
    _create_unique_if_missing(
        bind, "filings", "uq_filing_source_canonical_url", ["source_id", "canonical_url"]
    )

    for column in [
        Column("parser_version", String(64)),
        Column("page_count", Integer),
        Column("parse_warnings", JSON),
        Column("content_hash", String(128)),
    ]:
        _add_if_missing(bind, "documents", column)

    for column in [
        Column("filing_id", Integer),
        Column("source_url", Text),
        Column("parser_version", String(64)),
        Column("content_hash", String(128)),
    ]:
        _add_if_missing(bind, "document_chunks", column)

    if not inspect(bind).has_table("company_source_identifiers"):
        op.create_table(
            "company_source_identifiers",
            Column("id", Integer, primary_key=True),
            Column("company_id", Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            Column("source_id", String(128), nullable=False),
            Column("external_issuer_id", String(255)),
            Column("external_symbol", String(64)),
            Column("exchange", String(32)),
            Column("market", String(64)),
            Column("issuer_name", String(255)),
            Column("current_name", String(255)),
            Column("historical_names", JSON),
            Column("listing_status", String(64)),
            Column("valid_from", String(32)),
            Column("valid_to", String(32)),
            Column("is_current", Boolean, default=True),
            Column("metadata", JSON),
            Column("verified_at", String(64)),
            Column("created_at", DateTime),
        )
    _create_index_if_missing(
        bind, "company_source_identifiers", "ix_company_source_identifiers_source_id", ["source_id"]
    )
    _create_index_if_missing(
        bind,
        "company_source_identifiers",
        "ix_company_source_identifiers_external_issuer_id",
        ["external_issuer_id"],
    )
    _create_index_if_missing(
        bind,
        "company_source_identifiers",
        "ix_company_source_identifiers_external_symbol",
        ["external_symbol"],
    )
    _create_index_if_missing(
        bind, "company_source_identifiers", "ix_company_source_identifiers_exchange", ["exchange"]
    )
    _create_unique_if_missing(
        bind,
        "company_source_identifiers",
        "uq_company_source_identifier",
        ["source_id", "external_issuer_id", "external_symbol", "exchange"],
    )

    if not inspect(bind).has_table("data_quality_issues"):
        op.create_table(
            "data_quality_issues",
            Column("id", Integer, primary_key=True),
            Column("issue_type", String(128), nullable=False),
            Column("severity", String(64), nullable=False, server_default="medium"),
            Column("entity_type", String(64), nullable=False),
            Column("entity_id", String(128)),
            Column("symbol", String(32)),
            Column("source_id", String(128)),
            Column("status", String(64), nullable=False, server_default="open"),
            Column("details", JSON),
            Column("first_seen_at", DateTime),
            Column("last_seen_at", DateTime),
            Column("resolved_at", DateTime),
            Column("resolution_note", Text),
        )
    for index_name, columns in [
        ("ix_data_quality_issues_issue_type", ["issue_type"]),
        ("ix_data_quality_issues_severity", ["severity"]),
        ("ix_data_quality_issues_entity_type", ["entity_type"]),
        ("ix_data_quality_issues_entity_id", ["entity_id"]),
        ("ix_data_quality_issues_symbol", ["symbol"]),
        ("ix_data_quality_issues_source_id", ["source_id"]),
        ("ix_data_quality_issues_status", ["status"]),
    ]:
        _create_index_if_missing(bind, "data_quality_issues", index_name, columns)
    _create_unique_if_missing(
        bind,
        "data_quality_issues",
        "uq_data_quality_issue_entity",
        ["issue_type", "entity_type", "entity_id", "source_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("data_quality_issues", "company_source_identifiers"):
        if inspect(bind).has_table(table_name):
            op.drop_table(table_name)

    for table_name, column_name in [
        ("document_chunks", "content_hash"),
        ("document_chunks", "parser_version"),
        ("document_chunks", "source_url"),
        ("document_chunks", "filing_id"),
        ("documents", "content_hash"),
        ("documents", "parse_warnings"),
        ("documents", "page_count"),
        ("documents", "parser_version"),
        ("filings", "updated_at"),
        ("filings", "error_message"),
        ("filings", "error_type"),
        ("filings", "retry_count"),
        ("filings", "last_attempt_at"),
        ("filings", "retrieved_at"),
        ("filings", "source_tier"),
        ("filings", "verification_status"),
        ("filings", "raw_metadata_path"),
        ("filings", "last_modified"),
        ("filings", "etag"),
        ("filings", "sha256"),
        ("filings", "content_length"),
        ("filings", "content_type"),
        ("filings", "language"),
        ("filings", "original_filename"),
        ("filings", "download_url"),
        ("filings", "canonical_url"),
        ("filings", "published_at"),
        ("filings", "period_end"),
        ("filings", "period_start"),
        ("filings", "announcement_category"),
        ("filings", "document_type"),
        ("filings", "source_document_id"),
        ("filings", "source_id"),
        ("filings", "exchange"),
        ("filings", "symbol"),
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


def _create_index_if_missing(bind, table_name: str, index_name: str, columns: list[str]) -> None:
    indexes = {row["name"] for row in inspect(bind).get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def _create_unique_if_missing(
    bind, table_name: str, constraint_name: str, columns: list[str]
) -> None:
    constraints = {row["name"] for row in inspect(bind).get_unique_constraints(table_name)}
    if constraint_name not in constraints:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.create_unique_constraint(constraint_name, columns)
        else:
            op.create_unique_constraint(constraint_name, table_name, columns)
