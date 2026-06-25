from __future__ import annotations

from datetime import UTC, date, datetime

from app.models import EvidenceSnippet, LocalResearchBrief


def build_local_brief(
    query: str,
    snippets: list[EvidenceSnippet],
    *,
    as_of_date: date | None = None,
) -> LocalResearchBrief:
    missing: list[str] = []
    if not snippets:
        missing.append("No matching local evidence was found. Ingest more reports or broaden the query.")
    if snippets and not any(item.report_period for item in snippets):
        missing.append("Report periods are missing for some or all retrieved documents.")
    if snippets and not any(item.url for item in snippets):
        missing.append("Source URLs are missing for local files unless provided during ingestion.")

    return LocalResearchBrief(
        query=query,
        generated_at=datetime.now(UTC),
        as_of_date=as_of_date,
        snippets=snippets,
        assumptions=[
            "Local keyword retrieval is not a full semantic search engine.",
            "Retrieved text snippets are evidence leads and still require human review.",
        ],
        missing_information=missing,
    )


def render_local_brief(brief: LocalResearchBrief) -> str:
    lines: list[str] = [
        f"# Local Evidence Brief: {brief.query}",
        "",
        f"- Generated at: {brief.generated_at.isoformat()}",
    ]
    if brief.as_of_date:
        lines.append(f"- As-of date: {brief.as_of_date.isoformat()}")
    lines.extend(
        [
            "- Scope: local document library only",
            "- Advice boundary: research draft, not personalized investment advice",
            "",
            "## Executive Summary",
            "",
        ]
    )

    if brief.snippets:
        lines.append(
            "The local library returned evidence leads that may help answer the question. "
            "Review the cited files before using the findings in an investment memo."
        )
    else:
        lines.append("No local evidence matched the query.")

    lines.extend(["", "## Evidence Leads", ""])
    if brief.snippets:
        for index, snippet in enumerate(brief.snippets, start=1):
            lines.extend(_render_snippet(index, snippet))
    else:
        lines.append("- No snippets found.")

    lines.extend(["", "## Assumptions", ""])
    lines.extend(f"- {item}" for item in brief.assumptions)

    lines.extend(["", "## Missing Information", ""])
    if brief.missing_information:
        lines.extend(f"- {item}" for item in brief.missing_information)
    else:
        lines.append("- No obvious metadata gaps were detected in the retrieved snippets.")

    lines.extend(
        [
            "",
            "## Verification Checklist",
            "",
            "- Confirm the legal entity, ticker, exchange, and reporting currency.",
            "- Confirm whether dates refer to the reporting period or publication date.",
            "- Recompute material ratios from source statements before relying on them.",
            "- Verify any connector or web-derived claim against primary filings or issuer documents.",
            "- Record what evidence would falsify the thesis.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _render_snippet(index: int, snippet: EvidenceSnippet) -> list[str]:
    citation_parts = [snippet.source_path]
    if snippet.url:
        citation_parts.append(snippet.url)
    if snippet.report_period:
        citation_parts.append(f"report period: {snippet.report_period}")
    if snippet.publication_date:
        citation_parts.append(f"published: {snippet.publication_date}")

    excerpt = snippet.text.strip().replace("\n", " ")
    if len(excerpt) > 700:
        excerpt = excerpt[:697].rstrip() + "..."

    return [
        f"### {index}. {snippet.title}",
        "",
        f"- Score: {snippet.score:.2f}",
        f"- Citation: {' | '.join(citation_parts)}",
        "",
        "> " + excerpt,
        "",
    ]
