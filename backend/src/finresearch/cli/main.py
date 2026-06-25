from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from finresearch.database.session import get_library_path
from finresearch.services.company_analysis import CompanyAnalysisService
from finresearch.services.company_sync import SyncCompanyService
from finresearch.services.job_service import JobService
from finresearch.services.research_service import ResearchService


app = typer.Typer(help="Fin Research Agent product backend CLI")
console = Console()


@app.command()
def sync(
    symbol: Annotated[str, typer.Argument(help="A-share symbol")],
    years: Annotated[int, typer.Option(help="Years to sync")] = 5,
) -> None:
    result = SyncCompanyService(get_library_path()).execute(symbol, years=years)
    console.print_json(data=result.__dict__)


@app.command()
def analyze(
    symbol: Annotated[str, typer.Argument(help="A-share symbol")],
    years: Annotated[int, typer.Option(help="Years to analyze")] = 5,
    output: Annotated[Path | None, typer.Option(help="Save Markdown report")] = None,
) -> None:
    run = ResearchService(get_library_path()).create_structured_run(symbol, years=years)
    console.print_json(data=run["structured_result"])
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(str(run["report_markdown"]), encoding="utf-8")


@app.command("analyze-json")
def analyze_json(
    symbol: Annotated[str, typer.Argument(help="A-share symbol")],
    years: Annotated[int, typer.Option(help="Years to analyze")] = 5,
) -> None:
    result = CompanyAnalysisService(get_library_path()).execute(symbol, years=years)
    console.print_json(data=result.__dict__)


@app.command("run-job-once")
def run_job_once() -> None:
    result = JobService(get_library_path()).run_next()
    console.print_json(data=result or {"status": "idle"})


def main() -> None:
    app()


if __name__ == "__main__":
    main()

