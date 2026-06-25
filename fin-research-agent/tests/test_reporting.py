from datetime import UTC, datetime

from app.models import EvidenceSnippet, LocalResearchBrief
from app.reporting import build_local_brief, render_local_brief


def test_build_local_brief_reports_missing_evidence() -> None:
    brief = build_local_brief("cash flow", [])

    assert brief.missing_information
    assert "No matching local evidence" in brief.missing_information[0]


def test_render_local_brief_includes_citation_and_checklist() -> None:
    brief = LocalResearchBrief(
        query="cash flow quality",
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        snippets=[
            EvidenceSnippet(
                document_id=1,
                chunk_id=0,
                title="Annual Report",
                source_path="/tmp/report.md",
                text="Operating cash flow exceeded net profit.",
                score=3.5,
                report_period="2024-FY",
            )
        ],
    )

    rendered = render_local_brief(brief)

    assert "# Local Evidence Brief: cash flow quality" in rendered
    assert "Annual Report" in rendered
    assert "report period: 2024-FY" in rendered
    assert "Verification Checklist" in rendered
