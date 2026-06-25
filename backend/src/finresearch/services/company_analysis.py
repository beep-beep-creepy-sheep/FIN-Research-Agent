from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.documents import DocumentRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.services.metric_calculator import calculate_metric_signals


@dataclass(frozen=True)
class AnalysisResult:
    symbol: str
    company: dict[str, object] | None
    periods: list[dict[str, object]]
    metrics: dict[str, object]
    quality_flags: list[str]
    evidence: list[dict[str, object]]
    data_gaps: list[str]
    generated_at: str


class CompanyAnalysisService:
    def __init__(self, library_path: Path) -> None:
        self.company_repo = CompanyRepository(library_path)
        self.fact_repo = FinancialFactRepository(library_path)
        self.document_repo = DocumentRepository(library_path)

    def execute(
        self,
        symbol: str,
        *,
        years: int = 5,
        as_of_date: str | None = None,
        strict_as_of: bool = False,
    ) -> AnalysisResult:
        matrix = self.fact_repo.matrix(symbol, years=years, as_of_date=as_of_date)
        metrics_result = calculate_metric_signals(matrix)
        evidence = [
            snippet.model_dump()
            for snippet in self.document_repo.search(symbol, limit=6)
        ]
        gaps: list[str] = []
        if not matrix:
            gaps.append("missing_structured_financial_facts")
        if not evidence:
            gaps.append("missing_local_document_evidence")
        if strict_as_of and as_of_date:
            # Repository filtering already applies publication_date <= as_of_date.
            gaps.append("strict_as_of_enabled_unknown_publication_dates_excluded")

        return AnalysisResult(
            symbol=symbol,
            company=self.company_repo.get(symbol),
            periods=matrix,
            metrics=dict(metrics_result["metrics"]),
            quality_flags=list(metrics_result["quality_flags"]),
            evidence=evidence,
            data_gaps=gaps,
            generated_at=datetime.now(UTC).isoformat(),
        )

