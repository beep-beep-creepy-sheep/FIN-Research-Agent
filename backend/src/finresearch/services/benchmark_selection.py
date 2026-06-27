from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from finresearch.database.models import Company, IndexQuote
from finresearch.database.session import session_scope


@dataclass(frozen=True)
class BenchmarkSelection:
    benchmark_code: str | None
    benchmark_name: str | None
    benchmark_source: str
    selection_reason: str
    selection_version: str = "stage3-benchmark-v1"
    missing_reason: str | None = None


class BenchmarkRegistry:
    def select(self, *, symbol: str, exchange: str | None, industry: str | None = None) -> BenchmarkSelection:
        clean = symbol.upper().split(".")[0]
        if exchange == "BSE" or clean.startswith(("8", "4")):
            return BenchmarkSelection("899050.BJ", "北证50", "configured_index_registry", "bse_board")
        if exchange == "SSE" and clean.startswith("688"):
            return BenchmarkSelection("000688.SH", "科创50", "configured_index_registry", "sse_star_board")
        if exchange == "SZSE" and clean.startswith("3"):
            return BenchmarkSelection("399006.SZ", "创业板指", "configured_index_registry", "szse_chinext_board")
        if exchange == "SSE":
            return BenchmarkSelection("000001.SH", "上证指数", "configured_index_registry", "sse_market_wide")
        if exchange == "SZSE":
            return BenchmarkSelection("399001.SZ", "深证成指", "configured_index_registry", "szse_market_wide")
        if industry:
            return BenchmarkSelection("000300.SH", "沪深300", "configured_index_registry", "fallback_cross_market_industry_unmapped")
        return BenchmarkSelection(
            None,
            None,
            "configured_index_registry",
            "no_exchange_or_board_mapping",
            missing_reason="benchmark_not_configured",
        )


class BenchmarkSelectionService:
    def select_for_symbol(self, symbol: str) -> dict[str, object]:
        with session_scope() as session:
            clean = symbol.upper()
            company = session.scalar(
                select(Company).where((Company.symbol == clean) | (Company.symbol.like(f"{clean}.%")))
            )
            exchange = company.exchange if company else _infer_exchange(symbol)
            industry = company.industry if company else None
            selection = BenchmarkRegistry().select(symbol=symbol, exchange=exchange, industry=industry)
            quote_count = 0
            if selection.benchmark_code:
                quote_count = session.scalar(
                    select(func.count(IndexQuote.id)).where(
                        IndexQuote.index_code == selection.benchmark_code
                    )
                ) or 0
        payload = selection.__dict__.copy()
        payload["quote_count"] = quote_count
        if selection.benchmark_code and quote_count == 0:
            payload["missing_reason"] = "benchmark_price_missing"
        return payload


def _infer_exchange(symbol: str) -> str | None:
    clean = symbol.upper().split(".")[0]
    if symbol.upper().endswith(".SH") or clean.startswith("6"):
        return "SSE"
    if symbol.upper().endswith(".BJ") or clean.startswith(("8", "4")):
        return "BSE"
    if symbol.upper().endswith(".SZ") or clean.startswith(("0", "2", "3")):
        return "SZSE"
    return None
