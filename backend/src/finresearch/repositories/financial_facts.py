from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.financial_store import infer_exchange
from app.models import FinancialFact
from finresearch.database.models import Company, FinancialFact as FinancialFactModel
from finresearch.database.session import session_scope


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
                FinancialFactModel.period_end.desc(), FinancialFactModel.metric_code
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
            by_period[period][str(row["metric_code"])] = row["value"]
        return [by_period[period] for period in sorted(by_period, reverse=True)]


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
        "data_source": fact.data_source,
        "retrieved_at": fact.retrieved_at,
    }
