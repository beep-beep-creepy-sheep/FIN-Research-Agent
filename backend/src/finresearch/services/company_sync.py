from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ashare_client import AShareDataError

from finresearch.data_sources.akshare_source import AShareDataSource
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository


@dataclass(frozen=True)
class SyncResult:
    symbol: str
    company_synced: bool
    facts_count: int
    prices_count: int
    warnings: list[str]


class SyncCompanyService:
    def __init__(self, library_path: Path) -> None:
        self.company_repo = CompanyRepository(library_path)
        self.fact_repo = FinancialFactRepository(library_path)
        self.price_repo = PriceRepository(library_path)
        self.source = AShareDataSource()

    def execute(self, symbol: str, years: int = 5, skip_prices: bool = False) -> SyncResult:
        warnings: list[str] = []
        company_synced = False
        facts_count = 0
        prices_count = 0

        try:
            company = self.source.fetch_company(symbol)
            self.company_repo.upsert(company)
            company_synced = True
        except AShareDataError as exc:
            warnings.append(f"company: {exc}")

        try:
            facts_count = self.fact_repo.upsert_many(
                self.source.fetch_financial_facts(symbol, years=years)
            )
        except AShareDataError as exc:
            warnings.append(f"financial_facts: {exc}")

        if not skip_prices:
            try:
                prices_count = self.price_repo.upsert_many(
                    self.source.fetch_prices(symbol, years=years)
                )
            except AShareDataError as exc:
                warnings.append(f"prices: {exc}")

        return SyncResult(
            symbol=symbol,
            company_synced=company_synced,
            facts_count=facts_count,
            prices_count=prices_count,
            warnings=warnings,
        )

