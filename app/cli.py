from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

from app.agent_reach import AgentReachClient
from app.calculator import calculate_ratios
from app.config import Settings, default_library_path
from app.document_store import DocumentStore
from app.models import DocumentMetadata, FinancialInputs, ResearchRequest
from app.openai_research import OpenAIResearchClient
from app.reporting import build_local_brief, render_local_brief
from app.sec_client import SECCompanyFactsClient

app = typer.Typer(help="Evidence-first financial research CLI")
console = Console()


@app.command()
def research(
    query: Annotated[str, typer.Argument(help="Research question")],
    domains: Annotated[
        str,
        typer.Option(help="Comma-separated allowed domains, e.g. sec.gov,investor.apple.com"),
    ] = "",
    as_of: Annotated[str | None, typer.Option(help="As-of date, YYYY-MM-DD")] = None,
    agent_reach: Annotated[
        bool,
        typer.Option("--agent-reach/--no-agent-reach", help="Add Agent Reach Exa results as leads"),
    ] = False,
    output: Annotated[Path | None, typer.Option(help="Save Markdown report")] = None,
) -> None:
    allowed_domains = [item.strip() for item in domains.split(",") if item.strip()]
    request = ResearchRequest(
        query=query,
        allowed_domains=allowed_domains,
        include_agent_reach=agent_reach,
        as_of_date=as_of,
    )

    connector_context = ""
    if agent_reach:
        reach = AgentReachClient()
        result = reach.exa_search(query, num_results=8)
        if result.ok:
            connector_context = result.stdout[:20_000]
        else:
            console.print(f"[yellow]Agent Reach unavailable:[/yellow] {result.stderr}")

    try:
        settings = Settings.from_env()
        report = OpenAIResearchClient(settings).research(request, connector_context)
    except Exception as exc:  # CLI boundary: display a clear error instead of a traceback.
        console.print(f"[red]Research failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(Panel(report, title="Research report", border_style="blue"))
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        console.print(f"Saved to {output}")


@app.command("local-ingest")
def local_ingest(
    files: Annotated[list[Path], typer.Argument(help="Local files to index")],
    library: Annotated[Path, typer.Option(help="SQLite library path")] = default_library_path(),
    issuer: Annotated[str | None, typer.Option(help="Issuer or company name")] = None,
    report_period: Annotated[str | None, typer.Option(help="Report period, e.g. 2024-FY")] = None,
    publication_date: Annotated[str | None, typer.Option(help="Publication date, YYYY-MM-DD")] = None,
    url: Annotated[str | None, typer.Option(help="Source URL for citation")] = None,
) -> None:
    """Index local text/markdown/csv/json files, plus PDFs when pypdf is installed."""
    store = DocumentStore(library)
    for file_path in files:
        metadata = DocumentMetadata.from_path(file_path).model_copy(
            update={
                "issuer": issuer,
                "report_period": report_period,
                "publication_date": publication_date,
                "url": url,
            }
        )
        try:
            document_id = store.add_file(file_path, metadata)
        except Exception as exc:
            console.print(f"[red]Failed to ingest {file_path}:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(f"Indexed {file_path} as document {document_id}")


@app.command("library-list")
def library_list(
    library: Annotated[Path, typer.Option(help="SQLite library path")] = default_library_path(),
) -> None:
    store = DocumentStore(library)
    rows = store.list_documents()
    if not rows:
        console.print("No documents indexed yet.")
        return
    console.print_json(data=rows)


@app.command("local-search")
def local_search(
    query: Annotated[str, typer.Argument(help="Keyword query")],
    library: Annotated[Path, typer.Option(help="SQLite library path")] = default_library_path(),
    limit: Annotated[int, typer.Option(help="Maximum snippets")] = 8,
) -> None:
    store = DocumentStore(library)
    snippets = store.search(query, limit=limit)
    console.print_json(data=[snippet.model_dump() for snippet in snippets])


@app.command("local-brief")
def local_brief(
    query: Annotated[str, typer.Argument(help="Research question")],
    library: Annotated[Path, typer.Option(help="SQLite library path")] = default_library_path(),
    limit: Annotated[int, typer.Option(help="Maximum evidence snippets")] = 8,
    as_of: Annotated[str | None, typer.Option(help="As-of date, YYYY-MM-DD")] = None,
    output: Annotated[Path | None, typer.Option(help="Save Markdown report")] = None,
) -> None:
    store = DocumentStore(library)
    snippets = store.search(query, limit=limit)
    as_of_date = date.fromisoformat(as_of) if as_of else None
    report = render_local_brief(build_local_brief(query, snippets, as_of_date=as_of_date))
    console.print(Panel(report, title="Local evidence brief", border_style="green"))
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        console.print(f"Saved to {output}")


@app.command()
def ratios(
    json_file: Annotated[Path, typer.Argument(help="JSON file containing financial inputs")],
) -> None:
    raw = json.loads(json_file.read_text(encoding="utf-8"))
    data = FinancialInputs.model_validate(raw)
    console.print_json(data=calculate_ratios(data))


@app.command()
def ingest(
    files: Annotated[list[Path], typer.Argument(help="PDF/text files to add to a knowledge base")],
    vector_store_id: Annotated[
        str | None, typer.Option(help="Existing vector store ID; creates one when omitted")
    ] = None,
    name: Annotated[str, typer.Option(help="Name for a new vector store")] = "financial-reports",
) -> None:
    """Upload local reports for OpenAI File Search and print the vector store ID."""
    settings = Settings.from_env()
    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.timeout_seconds)

    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        console.print(f"[red]Files not found:[/red] {', '.join(missing)}")
        raise typer.Exit(code=2)

    store_id = vector_store_id
    if not store_id:
        store = client.vector_stores.create(name=name)
        store_id = store.id
        console.print(f"Created vector store: [bold]{store_id}[/bold]")

    uploaded_ids: list[str] = []
    for path in files:
        with path.open("rb") as handle:
            uploaded = client.files.create(file=handle, purpose="assistants")
        client.vector_stores.files.create(vector_store_id=store_id, file_id=uploaded.id)
        uploaded_ids.append(uploaded.id)
        console.print(f"Queued {path.name} ({uploaded.id})")

    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        listing = client.vector_stores.files.list(vector_store_id=store_id)
        statuses = {item.id: getattr(item, "status", "unknown") for item in listing.data}
        current = {file_id: statuses.get(file_id, "pending") for file_id in uploaded_ids}
        if all(status == "completed" for status in current.values()):
            console.print("[green]All files are ready.[/green]")
            console.print(f"Set: export OPENAI_VECTOR_STORE_ID='{store_id}'")
            return
        failed = {fid: status for fid, status in current.items() if status in {"failed", "cancelled"}}
        if failed:
            console.print(f"[red]Ingestion failed:[/red] {failed}")
            raise typer.Exit(code=1)
        time.sleep(2)

    console.print(
        f"[yellow]Upload is still processing.[/yellow] Vector store: {store_id}. "
        "Check it again later or run research after setting OPENAI_VECTOR_STORE_ID."
    )


@app.command("doctor")
def doctor_command() -> None:
    result = AgentReachClient().doctor()
    if result.ok:
        console.print(result.stdout)
    else:
        console.print(f"[red]Agent Reach check failed:[/red] {result.stderr}")
        raise typer.Exit(code=1)


@app.command("sec-facts")
def sec_facts(
    cik: Annotated[str, typer.Argument(help="SEC CIK, with or without leading zeros")],
    metric: Annotated[str, typer.Option(help="US-GAAP metric, e.g. Revenues")] = "Revenues",
    unit: Annotated[str, typer.Option(help="Unit key in SEC facts")] = "USD",
    form: Annotated[str | None, typer.Option(help="Optional filing form filter, e.g. 10-K")] = None,
    limit: Annotated[int, typer.Option(help="Maximum observations")] = 8,
    user_agent: Annotated[
        str,
        typer.Option(help="SEC-compliant User-Agent, e.g. name email@example.com"),
    ] = "fin-research-agent contact@example.com",
) -> None:
    client = SECCompanyFactsClient(user_agent=user_agent)
    try:
        facts = client.get_company_facts(cik)
        values = client.extract_us_gaap_metric(facts, metric, unit=unit, form=form, limit=limit)
    except Exception as exc:
        console.print(f"[red]SEC request failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print_json(data=values)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
