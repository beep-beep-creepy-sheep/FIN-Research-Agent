from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.database import connect, migrate
from app.models import CompanyRecord, FinancialFact, PriceRecord


class FinancialStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        migrate(self.path)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.path)

    def upsert_company(self, company: CompanyRecord) -> int:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO companies (
                    symbol, exchange, company_name, industry, currency, listing_date, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(symbol) DO UPDATE SET
                    exchange = excluded.exchange,
                    company_name = COALESCE(excluded.company_name, companies.company_name),
                    industry = COALESCE(excluded.industry, companies.industry),
                    currency = COALESCE(excluded.currency, companies.currency),
                    listing_date = COALESCE(excluded.listing_date, companies.listing_date),
                    status = COALESCE(excluded.status, companies.status),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    company.symbol,
                    company.exchange,
                    company.company_name,
                    company.industry,
                    company.currency,
                    company.listing_date,
                    company.status,
                ),
            )
            row = db.execute("SELECT id FROM companies WHERE symbol = ?", (company.symbol,)).fetchone()
        return int(row["id"])

    def get_company(self, symbol: str) -> dict[str, object] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM companies WHERE symbol = ?", (symbol,)).fetchone()
            if row is None:
                return None
            summary = dict(row)
            summary["facts_count"] = db.execute(
                "SELECT COUNT(*) AS count FROM financial_facts WHERE symbol = ?",
                (symbol,),
            ).fetchone()["count"]
            summary["prices_count"] = db.execute(
                "SELECT COUNT(*) AS count FROM prices WHERE symbol = ?",
                (symbol,),
            ).fetchone()["count"]
            summary["latest_fact_period"] = db.execute(
                "SELECT MAX(period_end) AS value FROM financial_facts WHERE symbol = ?",
                (symbol,),
            ).fetchone()["value"]
            summary["latest_price_date"] = db.execute(
                "SELECT MAX(trade_date) AS value FROM prices WHERE symbol = ?",
                (symbol,),
            ).fetchone()["value"]
        return summary

    def upsert_facts(self, facts: list[FinancialFact]) -> int:
        if not facts:
            return 0
        with self._connect() as db:
            company_ids = {
                fact.symbol: self._company_id_for_symbol(db, fact.symbol) for fact in facts
            }
            db.executemany(
                """
                INSERT INTO financial_facts (
                    company_id, symbol, metric_code, metric_name, value, unit, currency,
                    period_start, period_end, publication_date, report_type, statement_type,
                    is_consolidated, source_url, source_page, source_text, data_source, retrieved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, metric_code, period_end, report_type, statement_type, data_source)
                DO UPDATE SET
                    metric_name = excluded.metric_name,
                    value = excluded.value,
                    unit = excluded.unit,
                    currency = excluded.currency,
                    period_start = excluded.period_start,
                    publication_date = excluded.publication_date,
                    is_consolidated = excluded.is_consolidated,
                    source_url = excluded.source_url,
                    source_page = excluded.source_page,
                    source_text = excluded.source_text,
                    retrieved_at = excluded.retrieved_at
                """,
                [
                    (
                        company_ids[fact.symbol],
                        fact.symbol,
                        fact.metric_code,
                        fact.metric_name,
                        fact.value,
                        fact.unit,
                        fact.currency,
                        fact.period_start,
                        fact.period_end,
                        fact.publication_date,
                        fact.report_type,
                        fact.statement_type,
                        1 if fact.is_consolidated else 0,
                        fact.source_url,
                        fact.source_page,
                        fact.source_text,
                        fact.data_source,
                        fact.retrieved_at,
                    )
                    for fact in facts
                ],
            )
        return len(facts)

    def upsert_prices(self, prices: list[PriceRecord]) -> int:
        if not prices:
            return 0
        with self._connect() as db:
            db.executemany(
                """
                INSERT INTO prices (
                    symbol, trade_date, open, high, low, close, volume, amount,
                    adjustment_type, data_source, retrieved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date, adjustment_type, data_source)
                DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    amount = excluded.amount,
                    retrieved_at = excluded.retrieved_at
                """,
                [
                    (
                        price.symbol,
                        price.trade_date,
                        price.open,
                        price.high,
                        price.low,
                        price.close,
                        price.volume,
                        price.amount,
                        price.adjustment_type,
                        price.data_source,
                        price.retrieved_at,
                    )
                    for price in prices
                ],
            )
        return len(prices)

    def facts(
        self,
        symbol: str,
        *,
        years: int | None = None,
        as_of_date: str | None = None,
    ) -> list[dict[str, object]]:
        clauses = ["symbol = ?"]
        params: list[object] = [symbol]
        if as_of_date:
            clauses.append("(publication_date IS NULL OR publication_date <= ?)")
            params.append(as_of_date)
        sql = f"""
            SELECT *
            FROM financial_facts
            WHERE {' AND '.join(clauses)}
            ORDER BY period_end DESC, metric_code
        """
        with self._connect() as db:
            rows = [dict(row) for row in db.execute(sql, params).fetchall()]
        if years is None:
            return rows
        periods = sorted({str(row["period_end"]) for row in rows}, reverse=True)[:years]
        return [row for row in rows if row["period_end"] in periods]

    def fact_matrix(
        self, symbol: str, *, years: int = 5, as_of_date: str | None = None
    ) -> list[dict[str, object]]:
        rows = self.facts(symbol, years=years, as_of_date=as_of_date)
        by_period: dict[str, dict[str, object]] = defaultdict(dict)
        for row in rows:
            period = str(row["period_end"])
            by_period[period]["period_end"] = period
            by_period[period][str(row["metric_code"])] = row["value"]
        return [by_period[period] for period in sorted(by_period, reverse=True)]

    def add_watchlist(self, symbol: str, note: str | None = None) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO watchlist (symbol, note)
                VALUES (?, ?)
                ON CONFLICT(symbol) DO UPDATE SET note = COALESCE(excluded.note, watchlist.note)
                """,
                (symbol, note),
            )

    def list_watchlist(self) -> list[dict[str, object]]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM watchlist ORDER BY symbol")]

    def record_sync_error(
        self, symbol: str, stage: str, message: str, data_source: str | None = None
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO sync_errors (symbol, stage, message, data_source)
                VALUES (?, ?, ?, ?)
                """,
                (symbol, stage, message, data_source),
            )

    def save_research_run(
        self, query: str, symbol: str | None, as_of_date: str | None, markdown: str
    ) -> int:
        with self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO research_runs (query, symbol, as_of_date, result_markdown)
                VALUES (?, ?, ?, ?)
                """,
                (query, symbol, as_of_date, markdown),
            )
        return int(cursor.lastrowid)

    def _company_id_for_symbol(self, db: sqlite3.Connection, symbol: str) -> int:
        row = db.execute("SELECT id FROM companies WHERE symbol = ?", (symbol,)).fetchone()
        if row is not None:
            return int(row["id"])
        db.execute(
            """
            INSERT INTO companies (symbol, exchange, company_name, currency)
            VALUES (?, ?, ?, ?)
            """,
            (symbol, infer_exchange(symbol), symbol, "CNY"),
        )
        row = db.execute("SELECT id FROM companies WHERE symbol = ?", (symbol,)).fetchone()
        return int(row["id"])


def infer_exchange(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return "SSE"
    if symbol.startswith(("0", "2", "3")):
        return "SZSE"
    if symbol.startswith(("4", "8")):
        return "BSE"
    return "UNKNOWN"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
