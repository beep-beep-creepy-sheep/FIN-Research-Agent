from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from finresearch.api.dependencies import library_path
from finresearch.repositories.financial_facts import FinancialFactRepository


router = APIRouter()


@router.get("/{symbol}/financials")
def get_financials(
    symbol: str,
    years: int = 5,
    as_of: str | None = None,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return FinancialFactRepository(db_path).list_by_symbol(symbol, years=years, as_of_date=as_of)


@router.get("/{symbol}/metrics")
def get_metrics(
    symbol: str,
    years: int = 5,
    as_of: str | None = None,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return FinancialFactRepository(db_path).matrix(symbol, years=years, as_of_date=as_of)

