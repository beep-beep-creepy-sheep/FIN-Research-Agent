from __future__ import annotations

from sqlalchemy import or_, select

from app.models import CompanyRecord
from finresearch.database.models import Company
from finresearch.database.session import session_scope


class CompanyRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def get(self, symbol: str) -> dict[str, object] | None:
        with session_scope() as session:
            company = session.scalar(select(Company).where(Company.symbol == symbol))
            if company is None:
                return None
            summary = _company_dict(company)
            summary["facts_count"] = len(company.facts)
            summary["prices_count"] = len(company.prices)
            summary["latest_fact_period"] = max((fact.period_end for fact in company.facts), default=None)
            summary["latest_price_date"] = max((price.trade_date for price in company.prices), default=None)
            return summary

    def search(self, query: str) -> list[dict[str, object]]:
        pattern = f"%{query}%"
        with session_scope() as session:
            companies = session.scalars(
                select(Company)
                .where(or_(Company.symbol.like(pattern), Company.company_name.like(pattern)))
                .order_by(Company.symbol)
                .limit(20)
            ).all()
            return [_company_dict(company) for company in companies]

    def upsert(self, company: CompanyRecord) -> int:
        with session_scope() as session:
            saved = session.scalar(select(Company).where(Company.symbol == company.symbol))
            if saved is None:
                saved = Company(symbol=company.symbol)
                session.add(saved)
            saved.exchange = company.exchange
            saved.company_name = company.company_name or saved.company_name
            saved.industry = company.industry or saved.industry
            saved.currency = company.currency or saved.currency
            saved.listing_date = company.listing_date or saved.listing_date
            saved.status = company.status or saved.status
            session.flush()
            return int(saved.id)


def _company_dict(company: Company) -> dict[str, object]:
    return {
        "id": company.id,
        "symbol": company.symbol,
        "exchange": company.exchange,
        "company_name": company.company_name,
        "industry": company.industry,
        "currency": company.currency,
        "listing_date": company.listing_date,
        "status": company.status,
        "created_at": company.created_at.isoformat() if company.created_at else None,
        "updated_at": company.updated_at.isoformat() if company.updated_at else None,
    }
