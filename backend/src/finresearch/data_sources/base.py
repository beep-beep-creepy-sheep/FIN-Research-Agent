from __future__ import annotations

from typing import Protocol

from app.models import CompanyRecord, FinancialFact, PriceRecord


class EquityDataSource(Protocol):
    def fetch_company(self, symbol: str) -> CompanyRecord: ...

    def fetch_financial_facts(self, symbol: str, years: int = 5) -> list[FinancialFact]: ...

    def fetch_prices(self, symbol: str, years: int = 5) -> list[PriceRecord]: ...

