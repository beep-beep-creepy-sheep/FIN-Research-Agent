from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    exchange: Mapped[str | None] = mapped_column(String(32))
    company_name: Mapped[str | None] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str | None] = mapped_column(String(16), default="CNY")
    listing_date: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    facts: Mapped[list[FinancialFact]] = relationship(back_populates="company")
    prices: Mapped[list[Price]] = relationship(back_populates="company")


class Filing(Base):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    filing_type: Mapped[str | None] = mapped_column(String(64))
    report_period: Mapped[str | None] = mapped_column(String(64))
    publication_date: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(500))
    source_name: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(128))
    download_status: Mapped[str | None] = mapped_column(String(64))
    parse_status: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FinancialFact(Base):
    __tablename__ = "financial_facts"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "metric_code",
            "period_end",
            "report_type",
            "statement_type",
            "data_source",
            name="uq_financial_fact_current_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    filing_id: Mapped[int | None] = mapped_column(ForeignKey("filings.id", ondelete="SET NULL"))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    metric_code: Mapped[str] = mapped_column(String(128), index=True)
    metric_name: Mapped[str] = mapped_column(String(255))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    period_start: Mapped[str | None] = mapped_column(String(32))
    period_end: Mapped[str] = mapped_column(String(32), index=True)
    publication_date: Mapped[str | None] = mapped_column(String(32), index=True)
    report_type: Mapped[str | None] = mapped_column(String(64))
    statement_type: Mapped[str | None] = mapped_column(String(64))
    statement_scope: Mapped[str | None] = mapped_column(String(64), default="consolidated")
    is_consolidated: Mapped[bool] = mapped_column(Boolean, default=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_text: Mapped[str | None] = mapped_column(Text)
    source_priority: Mapped[int | None] = mapped_column(Integer, default=50)
    quality_status: Mapped[str | None] = mapped_column(String(64), default="unverified")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    data_source: Mapped[str] = mapped_column(String(128), index=True)
    retrieved_at: Mapped[str] = mapped_column(String(64))

    company: Mapped[Company | None] = relationship(back_populates="facts")


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "trade_date",
            "adjustment_type",
            "data_source",
            name="uq_price_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    trade_date: Mapped[str] = mapped_column(String(32), index=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    adjustment_type: Mapped[str] = mapped_column(String(32), default="none")
    data_source: Mapped[str] = mapped_column(String(128))
    retrieved_at: Mapped[str] = mapped_column(String(64))

    company: Mapped[Company | None] = relationship(back_populates="prices")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filing_id: Mapped[int | None] = mapped_column(ForeignKey("filings.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    source_path: Mapped[str | None] = mapped_column(Text, unique=True)
    source_type: Mapped[str | None] = mapped_column(String(64))
    issuer: Mapped[str | None] = mapped_column(String(255))
    report_period: Mapped[str | None] = mapped_column(String(64))
    publication_date: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str | None] = mapped_column(String(16))
    unit: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    document_type: Mapped[str | None] = mapped_column(String(64))
    parse_status: Mapped[str | None] = mapped_column(String(64), default="parsed")
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(Text)
    start_char: Mapped[int | None] = mapped_column(Integer)
    end_char: Mapped[int | None] = mapped_column(Integer)

    document: Mapped[Document] = relationship(back_populates="chunks")


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)
    question: Mapped[str | None] = mapped_column(Text)
    query: Mapped[str | None] = mapped_column(Text)
    as_of_date: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str | None] = mapped_column(String(64), default="completed")
    job_id: Mapped[int | None] = mapped_column(Integer, index=True)
    structured_result: Mapped[dict | None] = mapped_column(JSON)
    report_markdown: Mapped[str | None] = mapped_column(Text)
    result_markdown: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_run_id: Mapped[int | None] = mapped_column(ForeignKey("research_runs.id", ondelete="CASCADE"))
    claim: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    page_number: Mapped[int | None] = mapped_column(Integer)
    support_status: Mapped[str | None] = mapped_column(String(64))


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, default="Default")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_stage: Mapped[str | None] = mapped_column(String(128))
    error_type: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class SyncError(Base):
    __tablename__ = "sync_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str | None] = mapped_column(String(32))
    stage: Mapped[str] = mapped_column(String(128))
    error_type: Mapped[str | None] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text)
    data_source: Mapped[str | None] = mapped_column(String(128))
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExternalSource(Base):
    __tablename__ = "external_sources"
    __table_args__ = (UniqueConstraint("platform", "url", name="uq_external_source_platform_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector: Mapped[str] = mapped_column(String(128), index=True)
    platform: Mapped[str] = mapped_column(String(128), index=True)
    external_id: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[str | None] = mapped_column(String(64))
    fetched_at: Mapped[str] = mapped_column(String(64))
    content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    trust_level: Mapped[str] = mapped_column(String(64), default="unknown")
    verification_status: Mapped[str] = mapped_column(String(64), default="unverified")
    raw_file_path: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class CompanyExternalSource(Base):
    __tablename__ = "company_external_sources"
    __table_args__ = (UniqueConstraint("company_id", "external_source_id", name="uq_company_external_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    external_source_id: Mapped[int] = mapped_column(
        ForeignKey("external_sources.id", ondelete="CASCADE")
    )
    relationship_type: Mapped[str] = mapped_column(String(128))
    relevance_score: Mapped[float | None] = mapped_column(Float)


class ConnectorStatus(Base):
    __tablename__ = "connector_status"

    connector: Mapped[str] = mapped_column(String(128), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    configured: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_login: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(64), default="unknown")
    active_backend: Mapped[str | None] = mapped_column(String(128))
    last_checked_at: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(Text)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_after: Mapped[str | None] = mapped_column(String(64))


class MetricDefinitionModel(Base):
    __tablename__ = "metric_definitions"

    code: Mapped[str] = mapped_column(String(128), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(255))
    name_zh: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(128), index=True)
    formula: Mapped[str] = mapped_column(Text)
    inputs: Mapped[list[str]] = mapped_column(JSON)
    unit: Mapped[str] = mapped_column(String(64))
    periodicity: Mapped[str] = mapped_column(String(64))
    source_requirement: Mapped[str] = mapped_column(Text)
    missing_behavior: Mapped[str] = mapped_column(String(64), default="mark_missing")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MetricObservation(Base):
    __tablename__ = "metric_observations"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "metric_code",
            "period_end",
            "scope",
            "data_source",
            name="uq_metric_observation_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    metric_code: Mapped[str] = mapped_column(String(128), index=True)
    period_end: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str | None] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(64), default="company")
    formula: Mapped[str | None] = mapped_column(Text)
    inputs: Mapped[dict | None] = mapped_column(JSON)
    source_fact_ids: Mapped[list[int] | None] = mapped_column(JSON)
    source_price_ids: Mapped[list[int] | None] = mapped_column(JSON)
    source_snapshot_id: Mapped[int | None] = mapped_column(Integer)
    data_source: Mapped[str] = mapped_column(String(128), default="finresearch_metric_engine")
    quality_status: Mapped[str] = mapped_column(String(64), default="calculated")
    missing_reason: Mapped[str | None] = mapped_column(Text)
    calculated_at: Mapped[str] = mapped_column(String(64))


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (UniqueConstraint("market", "snapshot_date", "data_source", name="uq_market_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(64), default="CN", index=True)
    snapshot_date: Mapped[str] = mapped_column(String(32), index=True)
    as_of: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64), default="draft")
    headline: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    data_quality: Mapped[dict] = mapped_column(JSON, default=dict)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    data_source: Mapped[str] = mapped_column(String(128), default="local_database")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IndexQuote(Base):
    __tablename__ = "index_quotes"
    __table_args__ = (UniqueConstraint("index_code", "trade_date", "data_source", name="uq_index_quote"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_code: Mapped[str] = mapped_column(String(32), index=True)
    index_name: Mapped[str | None] = mapped_column(String(255))
    market: Mapped[str | None] = mapped_column(String(64), index=True)
    trade_date: Mapped[str] = mapped_column(String(32), index=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    prev_close: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(128))
    retrieved_at: Mapped[str] = mapped_column(String(64))


class SecurityQuote(Base):
    __tablename__ = "security_quotes"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", "data_source", name="uq_security_quote"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    market: Mapped[str | None] = mapped_column(String(64), index=True)
    sector: Mapped[str | None] = mapped_column(String(128), index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    trade_date: Mapped[str] = mapped_column(String(32), index=True)
    close: Mapped[float | None] = mapped_column(Float)
    prev_close: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    pe: Mapped[float | None] = mapped_column(Float)
    pb: Mapped[float | None] = mapped_column(Float)
    ps: Mapped[float | None] = mapped_column(Float)
    turnover_rate: Mapped[float | None] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(128))
    retrieved_at: Mapped[str] = mapped_column(String(64))


class DailyBar(Base):
    __tablename__ = "daily_bars"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", "adjustment_type", "data_source", name="uq_daily_bar"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    market: Mapped[str | None] = mapped_column(String(64), index=True)
    trade_date: Mapped[str] = mapped_column(String(32), index=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    adjustment_type: Mapped[str] = mapped_column(String(32), default="none")
    data_source: Mapped[str] = mapped_column(String(128))
    retrieved_at: Mapped[str] = mapped_column(String(64))


class Sector(Base):
    __tablename__ = "sectors"
    __table_args__ = (UniqueConstraint("market", "sector_code", "data_source", name="uq_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(64), index=True)
    sector_code: Mapped[str] = mapped_column(String(128), index=True)
    sector_name: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer, default=1)
    parent_code: Mapped[str | None] = mapped_column(String(128))
    data_source: Mapped[str] = mapped_column(String(128))
    updated_at: Mapped[str] = mapped_column(String(64))


class SectorSnapshot(Base):
    __tablename__ = "sector_snapshots"
    __table_args__ = (UniqueConstraint("market", "sector_code", "trade_date", "data_source", name="uq_sector_snapshot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(64), index=True)
    sector_code: Mapped[str] = mapped_column(String(128), index=True)
    sector_name: Mapped[str] = mapped_column(String(255))
    trade_date: Mapped[str] = mapped_column(String(32), index=True)
    constituents_count: Mapped[int] = mapped_column(Integer, default=0)
    advance_count: Mapped[int] = mapped_column(Integer, default=0)
    decline_count: Mapped[int] = mapped_column(Integer, default=0)
    flat_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_change_pct: Mapped[float | None] = mapped_column(Float)
    median_change_pct: Mapped[float | None] = mapped_column(Float)
    total_amount: Mapped[float | None] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(128))
    retrieved_at: Mapped[str] = mapped_column(String(64))


class MarketBreadthSnapshot(Base):
    __tablename__ = "market_breadth_snapshots"
    __table_args__ = (UniqueConstraint("market", "trade_date", "data_source", name="uq_market_breadth"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(64), index=True)
    trade_date: Mapped[str] = mapped_column(String(32), index=True)
    universe_count: Mapped[int] = mapped_column(Integer, default=0)
    advance_count: Mapped[int] = mapped_column(Integer, default=0)
    decline_count: Mapped[int] = mapped_column(Integer, default=0)
    flat_count: Mapped[int] = mapped_column(Integer, default=0)
    limit_up_count: Mapped[int] = mapped_column(Integer, default=0)
    limit_down_count: Mapped[int] = mapped_column(Integer, default=0)
    above_ma20_count: Mapped[int] = mapped_column(Integer, default=0)
    above_ma60_count: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[float | None] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(128))
    retrieved_at: Mapped[str] = mapped_column(String(64))


class ScreenDefinition(Base):
    __tablename__ = "screen_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    sort: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ScreenResult(Base):
    __tablename__ = "screen_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    screen_definition_id: Mapped[int | None] = mapped_column(ForeignKey("screen_definitions.id", ondelete="SET NULL"))
    generated_at: Mapped[str] = mapped_column(String(64), index=True)
    universe: Mapped[str | None] = mapped_column(String(128))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    rows: Mapped[list[dict]] = mapped_column(JSON, default=list)
    data_quality: Mapped[dict] = mapped_column(JSON, default=dict)
