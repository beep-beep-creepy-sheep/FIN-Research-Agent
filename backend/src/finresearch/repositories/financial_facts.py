from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.financial_store import infer_exchange
from app.models import FinancialFact
from finresearch.database.models import Company, FinancialFact as FinancialFactModel
from finresearch.database.session import session_scope
from finresearch.metrics.context import FinancialPeriod


class FinancialFactRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def upsert_many(self, facts: list[FinancialFact]) -> int:
        if not facts:
            return 0
        with session_scope() as session:
            for fact in facts:
                company = session.scalar(select(Company).where(Company.symbol == fact.symbol))
                if company is None:
                    company = Company(
                        symbol=fact.symbol,
                        exchange=infer_exchange(fact.symbol),
                        company_name=fact.symbol,
                        currency=fact.currency or "CNY",
                    )
                    session.add(company)
                    session.flush()
                saved = session.scalar(
                    select(FinancialFactModel).where(
                        FinancialFactModel.symbol == fact.symbol,
                        FinancialFactModel.metric_code == fact.metric_code,
                        FinancialFactModel.period_end == fact.period_end,
                        FinancialFactModel.report_type == fact.report_type,
                        FinancialFactModel.statement_type == fact.statement_type,
                        FinancialFactModel.data_source == fact.data_source,
                    )
                )
                if saved is None:
                    saved = FinancialFactModel(
                        symbol=fact.symbol,
                        metric_code=fact.metric_code,
                        period_end=fact.period_end,
                        report_type=fact.report_type,
                        statement_type=fact.statement_type,
                        data_source=fact.data_source,
                    )
                    session.add(saved)
                saved.company_id = company.id
                saved.metric_name = fact.metric_name
                saved.value = fact.value
                saved.unit = fact.unit
                saved.currency = fact.currency
                saved.period_start = fact.period_start
                saved.publication_date = fact.publication_date
                saved.statement_scope = "consolidated" if fact.is_consolidated else "parent"
                saved.is_consolidated = fact.is_consolidated
                saved.source_url = fact.source_url
                saved.source_page = fact.source_page
                saved.source_text = fact.source_text
                saved.retrieved_at = fact.retrieved_at
        return len(facts)

    def list_by_symbol(
        self,
        symbol: str,
        *,
        years: int | None = None,
        as_of_date: str | None = None,
        strict_as_of: bool = False,
    ) -> list[dict[str, object]]:
        with session_scope() as session:
            statement = select(FinancialFactModel).where(FinancialFactModel.symbol == symbol)
            if as_of_date:
                if strict_as_of:
                    statement = statement.where(
                        FinancialFactModel.publication_date.is_not(None),
                        FinancialFactModel.publication_date <= as_of_date,
                    )
                else:
                    statement = statement.where(
                        (FinancialFactModel.publication_date.is_(None))
                        | (FinancialFactModel.publication_date <= as_of_date)
                    )
            statement = statement.order_by(
                FinancialFactModel.period_end.desc(),
                FinancialFactModel.metric_code,
                FinancialFactModel.is_current.desc(),
                FinancialFactModel.version.desc(),
                FinancialFactModel.source_priority.asc(),
            )
            rows = [_fact_dict(fact) for fact in session.scalars(statement).all()]
        if years is None:
            return rows
        periods = sorted({str(row["period_end"]) for row in rows}, reverse=True)[:years]
        return [row for row in rows if row["period_end"] in periods]

    def matrix(
        self,
        symbol: str,
        *,
        years: int = 5,
        as_of_date: str | None = None,
        strict_as_of: bool = False,
    ) -> list[dict[str, object]]:
        rows = self.list_by_symbol(
            symbol, years=years, as_of_date=as_of_date, strict_as_of=strict_as_of
        )
        by_period: dict[str, dict[str, object]] = defaultdict(dict)
        for row in rows:
            period = str(row["period_end"])
            by_period[period]["period_end"] = period
            if row.get("currency"):
                by_period[period]["currency"] = row["currency"]
            by_period[period][str(row["metric_code"])] = row["value"]
        return [by_period[period] for period in sorted(by_period, reverse=True)]

    def periods(
        self,
        symbol: str,
        *,
        years: int | None = None,
        as_of_date: str | None = None,
        strict_as_of: bool = False,
    ) -> list[FinancialPeriod]:
        rows = self.list_by_symbol(
            symbol, years=years, as_of_date=as_of_date, strict_as_of=strict_as_of
        )
        chosen: dict[tuple[str, str, str | None, str | None, str | None], dict[str, object]] = {}
        for row in rows:
            period_end = str(row["period_end"])
            metric_code = str(row["metric_code"])
            report_type = _str_or_none(row.get("report_type"))
            statement_type = _str_or_none(row.get("statement_type"))
            statement_scope = _str_or_none(row.get("statement_scope"))
            key = (
                period_end,
                metric_code,
                report_type,
                statement_type,
                statement_scope,
            )
            current = chosen.get(key)
            if current is None or _fact_rank(row) > _fact_rank(current):
                chosen[key] = row

        by_period: dict[tuple[str, str | None, str | None], list[dict[str, object]]] = defaultdict(list)
        for row in chosen.values():
            period_key = str(row["period_end"])
            report_type_key = _str_or_none(row.get("report_type"))
            scope_key = _str_or_none(row.get("statement_scope"))
            by_period[(period_key, report_type_key, scope_key)].append(row)

        periods: list[FinancialPeriod] = []
        for (_period_end, _report_type, _scope), group in by_period.items():
            first = group[0]
            values: dict[str, float] = {}
            fact_ids: dict[str, tuple[int, ...]] = {}
            urls: dict[str, tuple[str, ...]] = {}
            pages: dict[str, tuple[int, ...]] = {}
            for row in group:
                code = str(row["metric_code"])
                value = row.get("value")
                if isinstance(value, int | float):
                    values[code] = float(value)
                row_id = row.get("id")
                if isinstance(row_id, int):
                    fact_ids[code] = (row_id,)
                source_url = row.get("source_url")
                if isinstance(source_url, str) and source_url:
                    urls[code] = (source_url,)
                source_page = row.get("source_page")
                if isinstance(source_page, int):
                    pages[code] = (source_page,)
            periods.append(
                FinancialPeriod(
                    symbol=str(first["symbol"]),
                    period_start=_str_or_none(first.get("period_start")),
                    period_end=str(first["period_end"]),
                    publication_date=_str_or_none(first.get("publication_date")),
                    report_type=_str_or_none(first.get("report_type")),
                    statement_type=_str_or_none(first.get("statement_type")),
                    statement_scope=_str_or_none(first.get("statement_scope")),
                    is_consolidated=bool(first.get("is_consolidated")),
                    currency=_str_or_none(first.get("currency")),
                    unit=_str_or_none(first.get("unit")),
                    data_source=_str_or_none(first.get("data_source")),
                    quality_status=_str_or_none(first.get("quality_status")),
                    version=_int_or_none(first.get("version")),
                    fact_ids_by_metric=fact_ids,
                    source_urls_by_metric=urls,
                    source_pages_by_metric=pages,
                    values=values,
                )
            )
        return sorted(periods, key=lambda period: period.period_end, reverse=True)


def _fact_dict(fact: FinancialFactModel) -> dict[str, object]:
    return {
        "id": fact.id,
        "company_id": fact.company_id,
        "symbol": fact.symbol,
        "metric_code": fact.metric_code,
        "metric_name": fact.metric_name,
        "value": fact.value,
        "unit": fact.unit,
        "currency": fact.currency,
        "period_start": fact.period_start,
        "period_end": fact.period_end,
        "publication_date": fact.publication_date,
        "report_type": fact.report_type,
        "statement_type": fact.statement_type,
        "statement_scope": fact.statement_scope,
        "is_consolidated": fact.is_consolidated,
        "source_url": fact.source_url,
        "source_page": fact.source_page,
        "source_text": fact.source_text,
        "source_priority": fact.source_priority,
        "quality_status": fact.quality_status,
        "version": fact.version,
        "is_current": fact.is_current,
        "data_source": fact.data_source,
        "retrieved_at": fact.retrieved_at,
    }


def _fact_rank(row: dict[str, object]) -> tuple[int, int, int]:
    current = 1 if row.get("is_current") is not False else 0
    version = _int_or_none(row.get("version")) or 0
    priority = _int_or_none(row.get("source_priority"))
    return current, version, -(priority if priority is not None else 50)


def _str_or_none(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None
