from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from finresearch.api.dependencies import library_path
from finresearch.repositories.companies import CompanyRepository
from finresearch.services.company_analysis import CompanyAnalysisService
from finresearch.services.company_charts import CompanyChartService
from finresearch.services.benchmark_selection import BenchmarkSelectionService


router = APIRouter()


@router.get("/search")
def search_companies(
    q: str = Query(..., min_length=1),
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return CompanyRepository(db_path).search(q)


@router.get("/{symbol}")
def get_company(symbol: str, db_path: Path = Depends(library_path)) -> dict[str, object]:
    company = CompanyRepository(db_path).get(symbol)
    if company is None:
        raise HTTPException(status_code=404, detail="company_not_found")
    return company


@router.get("/{symbol}/summary")
def get_company_summary(
    symbol: str,
    years: int = 5,
    as_of: str | None = None,
    db_path: Path = Depends(library_path),
) -> dict[str, object]:
    result = CompanyAnalysisService(db_path).execute(symbol, years=years, as_of_date=as_of)
    return result.__dict__


@router.get("/{symbol}/charts")
def get_company_charts(
    symbol: str,
    years: int = 10,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return CompanyChartService(db_path).build(symbol, years=years)


@router.get("/{symbol}/chart")
def get_company_chart_alias(
    symbol: str,
    years: int = 10,
    db_path: Path = Depends(library_path),
) -> list[dict[str, object]]:
    return CompanyChartService(db_path).build(symbol, years=years)


@router.get("/{symbol}/benchmark")
def get_company_benchmark(symbol: str) -> dict[str, object]:
    return BenchmarkSelectionService().select_for_symbol(symbol)
