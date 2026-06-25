from __future__ import annotations

from datetime import date
from pathlib import Path

from app.document_store import DocumentStore
from app.financial_store import FinancialStore
from app.models import EvidenceSnippet


CORE_METRICS = [
    "revenue",
    "net_profit",
    "net_profit_parent",
    "operating_cash_flow",
    "total_assets",
    "total_liabilities",
    "total_equity",
]


def build_structured_analysis(
    symbol: str,
    *,
    library_path: Path,
    years: int = 5,
    as_of_date: date | None = None,
) -> str:
    store = FinancialStore(library_path)
    document_store = DocumentStore(library_path)
    as_of_text = as_of_date.isoformat() if as_of_date else None
    company = store.get_company(symbol)
    matrix = store.fact_matrix(symbol, years=years, as_of_date=as_of_text)
    snippets = document_store.search(symbol, limit=5)

    lines: list[str] = [
        f"# Financial Analysis: {symbol}",
        "",
        f"- Years requested: {years}",
        f"- As-of date: {as_of_text or 'latest available'}",
        "- Scope: local SQLite facts and local document evidence first",
        "- Advice boundary: research draft, not personalized investment advice",
        "",
        "## Company Overview",
        "",
    ]
    if company:
        lines.extend(
            [
                f"- Name: {company.get('company_name') or symbol}",
                f"- Exchange: {company.get('exchange') or 'unknown'}",
                f"- Industry: {company.get('industry') or 'unknown'}",
                f"- Currency: {company.get('currency') or 'unknown'}",
                f"- Latest fact period: {company.get('latest_fact_period') or 'missing'}",
                f"- Latest price date: {company.get('latest_price_date') or 'missing'}",
            ]
        )
    else:
        lines.append("- Company profile is missing. Run `finresearch sync SYMBOL --years 5`.")

    lines.extend(["", "## Structured Financial Facts", ""])
    if matrix:
        lines.extend(_render_matrix(matrix))
    else:
        lines.append("No structured financial facts were found.")

    lines.extend(["", "## Calculated Signals", ""])
    lines.extend(_render_signals(matrix))

    lines.extend(["", "## Local Document Evidence", ""])
    if snippets:
        for index, snippet in enumerate(snippets, start=1):
            lines.extend(_render_snippet(index, snippet))
    else:
        lines.append("- No local document snippets matched the symbol.")

    lines.extend(
        [
            "",
            "## Data Gaps And Quality Risks",
            "",
            "- AKShare is a convenient aggregation source, not the final authority.",
            "- Material financial figures should be checked against exchange filings or issuer reports.",
            "- Missing publication dates can weaken as-of filtering and point-in-time analysis.",
            "- PDF table extraction may lose units, signs, merged cells, or page context.",
            "",
            "## Verification Checklist",
            "",
            "- Confirm company identity, exchange, currency, and consolidation scope.",
            "- Reconcile revenue, profit, operating cash flow, and equity against official annual reports.",
            "- Check report period versus publication date before using historical conclusions.",
            "- Verify latest major announcements and audit/regulatory risks from primary sources.",
            "- Record what evidence would falsify the investment thesis.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _render_matrix(matrix: list[dict[str, object]]) -> list[str]:
    header = ["Period"] + CORE_METRICS
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in matrix:
        values = [str(row.get("period_end", ""))]
        for metric in CORE_METRICS:
            values.append(_format_number(row.get(metric)))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _render_signals(matrix: list[dict[str, object]]) -> list[str]:
    if not matrix:
        return ["- Not enough structured data to calculate signals."]
    lines: list[str] = []
    latest = matrix[0]
    revenue = _to_float(latest.get("revenue"))
    net_profit = _to_float(latest.get("net_profit") or latest.get("net_profit_parent"))
    ocf = _to_float(latest.get("operating_cash_flow"))
    assets = _to_float(latest.get("total_assets"))
    liabilities = _to_float(latest.get("total_liabilities"))
    equity = _to_float(latest.get("total_equity"))

    if revenue and net_profit is not None:
        lines.append(f"- Net margin: {net_profit / revenue:.2%}")
    if net_profit and ocf is not None:
        lines.append(f"- Cash conversion: {ocf / net_profit:.2f}x")
    if assets and liabilities is not None:
        lines.append(f"- Liability ratio: {liabilities / assets:.2%}")
    if equity and net_profit is not None:
        lines.append(f"- ROE proxy: {net_profit / equity:.2%}")
    if not lines:
        lines.append("- Core facts are present but insufficient for ratio calculations.")
    return lines


def _render_snippet(index: int, snippet: EvidenceSnippet) -> list[str]:
    excerpt = snippet.text.replace("\n", " ").strip()
    if len(excerpt) > 500:
        excerpt = excerpt[:497].rstrip() + "..."
    return [
        f"### {index}. {snippet.title}",
        "",
        f"- Source: {snippet.source_path}",
        f"- Report period: {snippet.report_period or 'unknown'}",
        "",
        "> " + excerpt,
        "",
    ]


def _format_number(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return ""
    if abs(number) >= 100_000_000:
        return f"{number / 100_000_000:.2f}亿"
    if abs(number) >= 10_000:
        return f"{number / 10_000:.2f}万"
    return f"{number:.2f}"


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
