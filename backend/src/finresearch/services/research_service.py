from __future__ import annotations

from pathlib import Path

from finresearch.repositories.research import ResearchRepository
from finresearch.services.company_analysis import AnalysisResult, CompanyAnalysisService


class ResearchService:
    def __init__(self, library_path: Path) -> None:
        self.analysis_service = CompanyAnalysisService(library_path)
        self.research_repo = ResearchRepository(library_path)

    def create_structured_run(
        self,
        symbol: str,
        *,
        years: int = 5,
        as_of_date: str | None = None,
    ) -> dict[str, object]:
        result = self.analysis_service.execute(symbol, years=years, as_of_date=as_of_date)
        markdown = render_markdown(result)
        run_id = self.research_repo.save(
            query=f"analyze {symbol}",
            symbol=symbol,
            as_of_date=as_of_date,
            markdown=markdown,
        )
        return {"id": run_id, "structured_result": result.__dict__, "report_markdown": markdown}

    def list_runs(self) -> list[dict[str, object]]:
        return self.research_repo.list()


def render_markdown(result: AnalysisResult) -> str:
    company = result.company or {}
    lines = [
        f"# Research Report: {result.symbol}",
        "",
        f"- Company: {company.get('company_name') or result.symbol}",
        f"- Generated at: {result.generated_at}",
        "",
        "## Metrics",
        "",
    ]
    if result.metrics:
        lines.extend(f"- {key}: {value}" for key, value in result.metrics.items())
    else:
        lines.append("- No calculated metrics available.")

    lines.extend(["", "## Quality Flags", ""])
    lines.extend(f"- {item}" for item in (result.quality_flags or ["none"]))

    lines.extend(["", "## Data Gaps", ""])
    lines.extend(f"- {item}" for item in (result.data_gaps or ["none"]))
    return "\n".join(lines) + "\n"

