"""initial complete schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('symbol', sa.String(32), nullable=False, unique=True),
        sa.Column('exchange', sa.String(32)),
        sa.Column('company_name', sa.String(255)),
        sa.Column('industry', sa.String(255)),
        sa.Column('currency', sa.String(16)),
        sa.Column('listing_date', sa.String(32)),
        sa.Column('status', sa.String(32)),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_companies_company_name', 'companies', ['company_name'])
    op.create_index('ix_companies_symbol', 'companies', ['symbol'], unique=True)
    op.create_table(
        "connector_status",
        sa.Column('connector', sa.String(128), primary_key=True, nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('configured', sa.Boolean(), nullable=False),
        sa.Column('available', sa.Boolean(), nullable=False),
        sa.Column('requires_login', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(64), nullable=False),
        sa.Column('active_backend', sa.String(128)),
        sa.Column('last_checked_at', sa.String(64)),
        sa.Column('last_error', sa.Text()),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('retry_after', sa.String(64)),
    )
    op.create_table(
        "external_sources",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('connector', sa.String(128), nullable=False),
        sa.Column('platform', sa.String(128), nullable=False),
        sa.Column('external_id', sa.String(255)),
        sa.Column('title', sa.String(500)),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('author', sa.String(255)),
        sa.Column('published_at', sa.String(64)),
        sa.Column('fetched_at', sa.String(64), nullable=False),
        sa.Column('content', sa.Text()),
        sa.Column('content_hash', sa.String(128), nullable=False),
        sa.Column('trust_level', sa.String(64), nullable=False),
        sa.Column('verification_status', sa.String(64), nullable=False),
        sa.Column('raw_file_path', sa.Text()),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.UniqueConstraint('platform', 'url', name='uq_external_source_platform_url'),
    )
    op.create_index('ix_external_sources_connector', 'external_sources', ['connector'])
    op.create_index('ix_external_sources_content_hash', 'external_sources', ['content_hash'])
    op.create_index('ix_external_sources_platform', 'external_sources', ['platform'])
    op.create_table(
        "index_quotes",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('index_code', sa.String(32), nullable=False),
        sa.Column('index_name', sa.String(255)),
        sa.Column('market', sa.String(64)),
        sa.Column('trade_date', sa.String(32), nullable=False),
        sa.Column('open', sa.Float()),
        sa.Column('high', sa.Float()),
        sa.Column('low', sa.Float()),
        sa.Column('close', sa.Float()),
        sa.Column('prev_close', sa.Float()),
        sa.Column('change_pct', sa.Float()),
        sa.Column('volume', sa.Float()),
        sa.Column('amount', sa.Float()),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('retrieved_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('index_code', 'trade_date', 'data_source', name='uq_index_quote'),
    )
    op.create_index('ix_index_quotes_index_code', 'index_quotes', ['index_code'])
    op.create_index('ix_index_quotes_market', 'index_quotes', ['market'])
    op.create_index('ix_index_quotes_trade_date', 'index_quotes', ['trade_date'])
    op.create_table(
        "jobs",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('job_type', sa.String(64), nullable=False),
        sa.Column('status', sa.String(64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON()),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('current_stage', sa.String(128)),
        sa.Column('error_type', sa.String(128)),
        sa.Column('error_message', sa.Text()),
        sa.Column('failed_at', sa.DateTime()),
        sa.Column('retryable', sa.Boolean()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
    )
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_table(
        "market_breadth_snapshots",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('market', sa.String(64), nullable=False),
        sa.Column('trade_date', sa.String(32), nullable=False),
        sa.Column('universe_count', sa.Integer(), nullable=False),
        sa.Column('advance_count', sa.Integer(), nullable=False),
        sa.Column('decline_count', sa.Integer(), nullable=False),
        sa.Column('flat_count', sa.Integer(), nullable=False),
        sa.Column('limit_up_count', sa.Integer(), nullable=False),
        sa.Column('limit_down_count', sa.Integer(), nullable=False),
        sa.Column('above_ma20_count', sa.Integer(), nullable=False),
        sa.Column('above_ma60_count', sa.Integer(), nullable=False),
        sa.Column('total_amount', sa.Float()),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('retrieved_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('market', 'trade_date', 'data_source', name='uq_market_breadth'),
    )
    op.create_index('ix_market_breadth_snapshots_market', 'market_breadth_snapshots', ['market'])
    op.create_index('ix_market_breadth_snapshots_trade_date', 'market_breadth_snapshots', ['trade_date'])
    op.create_table(
        "market_snapshots",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('market', sa.String(64), nullable=False),
        sa.Column('snapshot_date', sa.String(32), nullable=False),
        sa.Column('as_of', sa.String(64), nullable=False),
        sa.Column('status', sa.String(64), nullable=False),
        sa.Column('headline', sa.Text()),
        sa.Column('summary', sa.JSON(), nullable=False),
        sa.Column('coverage', sa.JSON(), nullable=False),
        sa.Column('data_quality', sa.JSON(), nullable=False),
        sa.Column('source_count', sa.Integer(), nullable=False),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('market', 'snapshot_date', 'data_source', name='uq_market_snapshot'),
    )
    op.create_index('ix_market_snapshots_market', 'market_snapshots', ['market'])
    op.create_index('ix_market_snapshots_snapshot_date', 'market_snapshots', ['snapshot_date'])
    op.create_table(
        "metric_definitions",
        sa.Column('code', sa.String(128), primary_key=True, nullable=False),
        sa.Column('name_en', sa.String(255), nullable=False),
        sa.Column('name_zh', sa.String(255), nullable=False),
        sa.Column('category', sa.String(128), nullable=False),
        sa.Column('formula', sa.Text(), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=False),
        sa.Column('unit', sa.String(64), nullable=False),
        sa.Column('periodicity', sa.String(64), nullable=False),
        sa.Column('source_requirement', sa.Text(), nullable=False),
        sa.Column('missing_behavior', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_metric_definitions_category', 'metric_definitions', ['category'])
    op.create_table(
        "research_runs",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('symbol', sa.String(32)),
        sa.Column('question', sa.Text()),
        sa.Column('query', sa.Text()),
        sa.Column('as_of_date', sa.String(32)),
        sa.Column('status', sa.String(64)),
        sa.Column('job_id', sa.Integer()),
        sa.Column('structured_result', sa.JSON()),
        sa.Column('report_markdown', sa.Text()),
        sa.Column('result_markdown', sa.Text()),
        sa.Column('error_message', sa.Text()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_research_runs_job_id', 'research_runs', ['job_id'])
    op.create_index('ix_research_runs_symbol', 'research_runs', ['symbol'])
    op.create_table(
        "screen_definitions",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('filters', sa.JSON(), nullable=False),
        sa.Column('sort', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_screen_definitions_name', 'screen_definitions', ['name'])
    op.create_table(
        "sector_snapshots",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('market', sa.String(64), nullable=False),
        sa.Column('sector_code', sa.String(128), nullable=False),
        sa.Column('sector_name', sa.String(255), nullable=False),
        sa.Column('trade_date', sa.String(32), nullable=False),
        sa.Column('constituents_count', sa.Integer(), nullable=False),
        sa.Column('advance_count', sa.Integer(), nullable=False),
        sa.Column('decline_count', sa.Integer(), nullable=False),
        sa.Column('flat_count', sa.Integer(), nullable=False),
        sa.Column('avg_change_pct', sa.Float()),
        sa.Column('median_change_pct', sa.Float()),
        sa.Column('total_amount', sa.Float()),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('retrieved_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('market', 'sector_code', 'trade_date', 'data_source', name='uq_sector_snapshot'),
    )
    op.create_index('ix_sector_snapshots_market', 'sector_snapshots', ['market'])
    op.create_index('ix_sector_snapshots_sector_code', 'sector_snapshots', ['sector_code'])
    op.create_index('ix_sector_snapshots_trade_date', 'sector_snapshots', ['trade_date'])
    op.create_table(
        "sectors",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('market', sa.String(64), nullable=False),
        sa.Column('sector_code', sa.String(128), nullable=False),
        sa.Column('sector_name', sa.String(255), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('parent_code', sa.String(128)),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('updated_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('market', 'sector_code', 'data_source', name='uq_sector'),
    )
    op.create_index('ix_sectors_market', 'sectors', ['market'])
    op.create_index('ix_sectors_sector_code', 'sectors', ['sector_code'])
    op.create_table(
        "sync_errors",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('symbol', sa.String(32)),
        sa.Column('stage', sa.String(128), nullable=False),
        sa.Column('error_type', sa.String(128)),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data_source', sa.String(128)),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "watchlists",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "company_external_sources",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_source_id', sa.Integer(), sa.ForeignKey('external_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(128), nullable=False),
        sa.Column('relevance_score', sa.Float()),
        sa.UniqueConstraint('company_id', 'external_source_id', name='uq_company_external_source'),
    )
    op.create_table(
        "daily_bars",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE')),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('market', sa.String(64)),
        sa.Column('trade_date', sa.String(32), nullable=False),
        sa.Column('open', sa.Float()),
        sa.Column('high', sa.Float()),
        sa.Column('low', sa.Float()),
        sa.Column('close', sa.Float()),
        sa.Column('volume', sa.Float()),
        sa.Column('amount', sa.Float()),
        sa.Column('adjustment_type', sa.String(32), nullable=False),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('retrieved_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('symbol', 'trade_date', 'adjustment_type', 'data_source', name='uq_daily_bar'),
    )
    op.create_index('ix_daily_bars_market', 'daily_bars', ['market'])
    op.create_index('ix_daily_bars_symbol', 'daily_bars', ['symbol'])
    op.create_index('ix_daily_bars_trade_date', 'daily_bars', ['trade_date'])
    op.create_table(
        "filings",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE')),
        sa.Column('filing_type', sa.String(64)),
        sa.Column('report_period', sa.String(64)),
        sa.Column('publication_date', sa.String(32)),
        sa.Column('title', sa.String(500)),
        sa.Column('source_name', sa.String(128)),
        sa.Column('source_url', sa.Text()),
        sa.Column('local_path', sa.Text()),
        sa.Column('file_hash', sa.String(128)),
        sa.Column('download_status', sa.String(64)),
        sa.Column('parse_status', sa.String(64)),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "metric_observations",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE')),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('metric_code', sa.String(128), nullable=False),
        sa.Column('period_end', sa.String(32), nullable=False),
        sa.Column('value', sa.Float()),
        sa.Column('unit', sa.String(64)),
        sa.Column('currency', sa.String(16)),
        sa.Column('scope', sa.String(64), nullable=False),
        sa.Column('formula', sa.Text()),
        sa.Column('inputs', sa.JSON()),
        sa.Column('source_fact_ids', sa.JSON()),
        sa.Column('source_price_ids', sa.JSON()),
        sa.Column('source_snapshot_id', sa.Integer()),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('quality_status', sa.String(64), nullable=False),
        sa.Column('missing_reason', sa.Text()),
        sa.Column('calculated_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('symbol', 'metric_code', 'period_end', 'scope', 'data_source', name='uq_metric_observation_source'),
    )
    op.create_index('ix_metric_observations_metric_code', 'metric_observations', ['metric_code'])
    op.create_index('ix_metric_observations_period_end', 'metric_observations', ['period_end'])
    op.create_index('ix_metric_observations_symbol', 'metric_observations', ['symbol'])
    op.create_table(
        "prices",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE')),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('trade_date', sa.String(32), nullable=False),
        sa.Column('open', sa.Float()),
        sa.Column('high', sa.Float()),
        sa.Column('low', sa.Float()),
        sa.Column('close', sa.Float()),
        sa.Column('volume', sa.Float()),
        sa.Column('amount', sa.Float()),
        sa.Column('adjustment_type', sa.String(32), nullable=False),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('retrieved_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('symbol', 'trade_date', 'adjustment_type', 'data_source', name='uq_price_source'),
    )
    op.create_index('ix_prices_symbol', 'prices', ['symbol'])
    op.create_index('ix_prices_trade_date', 'prices', ['trade_date'])
    op.create_table(
        "screen_results",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('screen_definition_id', sa.Integer(), sa.ForeignKey('screen_definitions.id', ondelete='SET NULL')),
        sa.Column('generated_at', sa.String(64), nullable=False),
        sa.Column('universe', sa.String(128)),
        sa.Column('filters', sa.JSON(), nullable=False),
        sa.Column('result_count', sa.Integer(), nullable=False),
        sa.Column('rows', sa.JSON(), nullable=False),
        sa.Column('data_quality', sa.JSON(), nullable=False),
    )
    op.create_index('ix_screen_results_generated_at', 'screen_results', ['generated_at'])
    op.create_table(
        "security_quotes",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE')),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('market', sa.String(64)),
        sa.Column('sector', sa.String(128)),
        sa.Column('industry', sa.String(255)),
        sa.Column('trade_date', sa.String(32), nullable=False),
        sa.Column('close', sa.Float()),
        sa.Column('prev_close', sa.Float()),
        sa.Column('change_pct', sa.Float()),
        sa.Column('volume', sa.Float()),
        sa.Column('amount', sa.Float()),
        sa.Column('market_cap', sa.Float()),
        sa.Column('pe', sa.Float()),
        sa.Column('pb', sa.Float()),
        sa.Column('ps', sa.Float()),
        sa.Column('turnover_rate', sa.Float()),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('retrieved_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('symbol', 'trade_date', 'data_source', name='uq_security_quote'),
    )
    op.create_index('ix_security_quotes_market', 'security_quotes', ['market'])
    op.create_index('ix_security_quotes_sector', 'security_quotes', ['sector'])
    op.create_index('ix_security_quotes_symbol', 'security_quotes', ['symbol'])
    op.create_index('ix_security_quotes_trade_date', 'security_quotes', ['trade_date'])
    op.create_table(
        "watchlist_items",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('watchlist_id', sa.Integer(), sa.ForeignKey('watchlists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('note', sa.Text()),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('watchlist_id', 'symbol', name='uq_watchlist_item'),
    )
    op.create_index('ix_watchlist_items_symbol', 'watchlist_items', ['symbol'])
    op.create_table(
        "documents",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('filing_id', sa.Integer(), sa.ForeignKey('filings.id', ondelete='SET NULL')),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('source_url', sa.Text()),
        sa.Column('local_path', sa.Text()),
        sa.Column('source_path', sa.Text(), unique=True),
        sa.Column('source_type', sa.String(64)),
        sa.Column('issuer', sa.String(255)),
        sa.Column('report_period', sa.String(64)),
        sa.Column('publication_date', sa.String(32)),
        sa.Column('currency', sa.String(16)),
        sa.Column('unit', sa.String(64)),
        sa.Column('url', sa.Text()),
        sa.Column('file_hash', sa.String(128)),
        sa.Column('document_type', sa.String(64)),
        sa.Column('parse_status', sa.String(64)),
        sa.Column('metadata_json', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_documents_file_hash', 'documents', ['file_hash'])
    op.create_table(
        "financial_facts",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id', ondelete='CASCADE')),
        sa.Column('filing_id', sa.Integer(), sa.ForeignKey('filings.id', ondelete='SET NULL')),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('metric_code', sa.String(128), nullable=False),
        sa.Column('metric_name', sa.String(255), nullable=False),
        sa.Column('value', sa.Float()),
        sa.Column('unit', sa.String(64)),
        sa.Column('currency', sa.String(16)),
        sa.Column('period_start', sa.String(32)),
        sa.Column('period_end', sa.String(32), nullable=False),
        sa.Column('publication_date', sa.String(32)),
        sa.Column('report_type', sa.String(64)),
        sa.Column('statement_type', sa.String(64)),
        sa.Column('statement_scope', sa.String(64)),
        sa.Column('is_consolidated', sa.Boolean(), nullable=False),
        sa.Column('source_url', sa.Text()),
        sa.Column('source_page', sa.Integer()),
        sa.Column('source_text', sa.Text()),
        sa.Column('source_priority', sa.Integer()),
        sa.Column('quality_status', sa.String(64)),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('data_source', sa.String(128), nullable=False),
        sa.Column('retrieved_at', sa.String(64), nullable=False),
        sa.UniqueConstraint('symbol', 'metric_code', 'period_end', 'report_type', 'statement_type', 'data_source', name='uq_financial_fact_current_source'),
    )
    op.create_index('ix_financial_facts_data_source', 'financial_facts', ['data_source'])
    op.create_index('ix_financial_facts_metric_code', 'financial_facts', ['metric_code'])
    op.create_index('ix_financial_facts_period_end', 'financial_facts', ['period_end'])
    op.create_index('ix_financial_facts_publication_date', 'financial_facts', ['publication_date'])
    op.create_index('ix_financial_facts_symbol', 'financial_facts', ['symbol'])
    op.create_table(
        "citations",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('research_run_id', sa.Integer(), sa.ForeignKey('research_runs.id', ondelete='CASCADE')),
        sa.Column('claim', sa.Text()),
        sa.Column('source_url', sa.Text()),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='SET NULL')),
        sa.Column('page_number', sa.Integer()),
        sa.Column('support_status', sa.String(64)),
    )
    op.create_table(
        "document_chunks",
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer()),
        sa.Column('section', sa.String(255)),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('search_vector', sa.Text()),
        sa.Column('start_char', sa.Integer()),
        sa.Column('end_char', sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table('document_chunks')
    op.drop_table('citations')
    op.drop_index('ix_financial_facts_symbol', table_name='financial_facts')
    op.drop_index('ix_financial_facts_publication_date', table_name='financial_facts')
    op.drop_index('ix_financial_facts_period_end', table_name='financial_facts')
    op.drop_index('ix_financial_facts_metric_code', table_name='financial_facts')
    op.drop_index('ix_financial_facts_data_source', table_name='financial_facts')
    op.drop_table('financial_facts')
    op.drop_index('ix_documents_file_hash', table_name='documents')
    op.drop_table('documents')
    op.drop_index('ix_watchlist_items_symbol', table_name='watchlist_items')
    op.drop_table('watchlist_items')
    op.drop_index('ix_security_quotes_trade_date', table_name='security_quotes')
    op.drop_index('ix_security_quotes_symbol', table_name='security_quotes')
    op.drop_index('ix_security_quotes_sector', table_name='security_quotes')
    op.drop_index('ix_security_quotes_market', table_name='security_quotes')
    op.drop_table('security_quotes')
    op.drop_index('ix_screen_results_generated_at', table_name='screen_results')
    op.drop_table('screen_results')
    op.drop_index('ix_prices_trade_date', table_name='prices')
    op.drop_index('ix_prices_symbol', table_name='prices')
    op.drop_table('prices')
    op.drop_index('ix_metric_observations_symbol', table_name='metric_observations')
    op.drop_index('ix_metric_observations_period_end', table_name='metric_observations')
    op.drop_index('ix_metric_observations_metric_code', table_name='metric_observations')
    op.drop_table('metric_observations')
    op.drop_table('filings')
    op.drop_index('ix_daily_bars_trade_date', table_name='daily_bars')
    op.drop_index('ix_daily_bars_symbol', table_name='daily_bars')
    op.drop_index('ix_daily_bars_market', table_name='daily_bars')
    op.drop_table('daily_bars')
    op.drop_table('company_external_sources')
    op.drop_table('watchlists')
    op.drop_table('sync_errors')
    op.drop_index('ix_sectors_sector_code', table_name='sectors')
    op.drop_index('ix_sectors_market', table_name='sectors')
    op.drop_table('sectors')
    op.drop_index('ix_sector_snapshots_trade_date', table_name='sector_snapshots')
    op.drop_index('ix_sector_snapshots_sector_code', table_name='sector_snapshots')
    op.drop_index('ix_sector_snapshots_market', table_name='sector_snapshots')
    op.drop_table('sector_snapshots')
    op.drop_index('ix_screen_definitions_name', table_name='screen_definitions')
    op.drop_table('screen_definitions')
    op.drop_index('ix_research_runs_symbol', table_name='research_runs')
    op.drop_index('ix_research_runs_job_id', table_name='research_runs')
    op.drop_table('research_runs')
    op.drop_index('ix_metric_definitions_category', table_name='metric_definitions')
    op.drop_table('metric_definitions')
    op.drop_index('ix_market_snapshots_snapshot_date', table_name='market_snapshots')
    op.drop_index('ix_market_snapshots_market', table_name='market_snapshots')
    op.drop_table('market_snapshots')
    op.drop_index('ix_market_breadth_snapshots_trade_date', table_name='market_breadth_snapshots')
    op.drop_index('ix_market_breadth_snapshots_market', table_name='market_breadth_snapshots')
    op.drop_table('market_breadth_snapshots')
    op.drop_index('ix_jobs_status', table_name='jobs')
    op.drop_table('jobs')
    op.drop_index('ix_index_quotes_trade_date', table_name='index_quotes')
    op.drop_index('ix_index_quotes_market', table_name='index_quotes')
    op.drop_index('ix_index_quotes_index_code', table_name='index_quotes')
    op.drop_table('index_quotes')
    op.drop_index('ix_external_sources_platform', table_name='external_sources')
    op.drop_index('ix_external_sources_content_hash', table_name='external_sources')
    op.drop_index('ix_external_sources_connector', table_name='external_sources')
    op.drop_table('external_sources')
    op.drop_table('connector_status')
    op.drop_index('ix_companies_symbol', table_name='companies')
    op.drop_index('ix_companies_company_name', table_name='companies')
    op.drop_table('companies')
