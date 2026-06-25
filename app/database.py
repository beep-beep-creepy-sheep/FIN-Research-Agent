from __future__ import annotations

import sqlite3
from pathlib import Path


MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filing_id INTEGER,
            title TEXT NOT NULL,
            source_path TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,
            issuer TEXT,
            report_period TEXT,
            publication_date TEXT,
            currency TEXT,
            unit TEXT,
            url TEXT,
            source_url TEXT,
            local_path TEXT,
            file_hash TEXT,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER,
            section TEXT,
            text TEXT NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            token_text TEXT NOT NULL,
            UNIQUE(document_id, chunk_index)
        );
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            exchange TEXT,
            company_name TEXT,
            industry TEXT,
            currency TEXT DEFAULT 'CNY',
            listing_date TEXT,
            status TEXT DEFAULT 'active',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            report_type TEXT,
            report_period TEXT,
            publication_date TEXT,
            source_url TEXT,
            local_path TEXT,
            file_hash TEXT,
            source_name TEXT,
            downloaded_at TEXT,
            UNIQUE(company_id, report_type, report_period, source_url)
        );

        CREATE TABLE IF NOT EXISTS financial_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            filing_id INTEGER REFERENCES filings(id) ON DELETE SET NULL,
            symbol TEXT NOT NULL,
            metric_code TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            value REAL,
            unit TEXT,
            currency TEXT,
            period_start TEXT,
            period_end TEXT NOT NULL,
            publication_date TEXT,
            report_type TEXT,
            statement_type TEXT,
            is_consolidated INTEGER NOT NULL DEFAULT 1,
            source_url TEXT,
            source_page INTEGER,
            source_text TEXT,
            data_source TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            UNIQUE(symbol, metric_code, period_end, report_type, statement_type, data_source)
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            adjustment_type TEXT NOT NULL DEFAULT 'none',
            data_source TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            UNIQUE(symbol, trade_date, adjustment_type, data_source)
        );

        CREATE TABLE IF NOT EXISTS research_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            symbol TEXT,
            as_of_date TEXT,
            result_markdown TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            research_run_id INTEGER REFERENCES research_runs(id) ON DELETE CASCADE,
            claim TEXT,
            source_url TEXT,
            document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
            page_number INTEGER,
            support_status TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            stage TEXT NOT NULL,
            message TEXT NOT NULL,
            data_source TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            note TEXT,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ),
    (
        3,
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text,
            title,
            issuer,
            tokenize='unicode61'
        );
        """,
    ),
]


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def migrate(path: Path) -> None:
    with connect(path) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = {
            int(row["version"])
            for row in db.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            db.executescript(sql)
            db.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone()
    return row is not None
