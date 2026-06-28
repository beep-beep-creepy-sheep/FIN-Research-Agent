from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from finresearch.services.analysis import AnalysisService, IndustryPackRegistry


router = APIRouter()


@router.get("/companies/{symbol}/analysis")
def get_company_analysis(
    symbol: str,
    as_of_date: str | None = None,
    strict_as_of: bool = False,
    include_markdown: bool = False,
    include_evidence: bool = True,
    industry_pack: str = Query(default="auto", pattern="^(auto|general|bank|consumer_manufacturing|consumer_or_manufacturing)$"),
) -> dict[str, object]:
    return _build(
        symbol,
        as_of_date=as_of_date,
        strict_as_of=strict_as_of,
        include_markdown=include_markdown,
        include_evidence=include_evidence,
        industry_pack=industry_pack,
    )


@router.get("/companies/{symbol}/analysis/findings")
def get_company_analysis_findings(
    symbol: str,
    as_of_date: str | None = None,
    strict_as_of: bool = False,
    industry_pack: str = "auto",
) -> dict[str, object]:
    report = _build(
        symbol,
        as_of_date=as_of_date,
        strict_as_of=strict_as_of,
        include_markdown=False,
        include_evidence=True,
        industry_pack=industry_pack,
    )
    return {"symbol": symbol, "findings": _all_findings(report)}


@router.get("/companies/{symbol}/analysis/report")
def get_company_analysis_report(
    symbol: str,
    as_of_date: str | None = None,
    strict_as_of: bool = False,
    include_markdown: bool = True,
    industry_pack: str = "auto",
) -> dict[str, object]:
    return _build(
        symbol,
        as_of_date=as_of_date,
        strict_as_of=strict_as_of,
        include_markdown=include_markdown,
        include_evidence=True,
        industry_pack=industry_pack,
    )


@router.get("/companies/{symbol}/analysis/quality")
def get_company_analysis_quality(
    symbol: str,
    as_of_date: str | None = None,
    strict_as_of: bool = False,
) -> dict[str, object]:
    report = _build(
        symbol,
        as_of_date=as_of_date,
        strict_as_of=strict_as_of,
        include_markdown=False,
        include_evidence=False,
        industry_pack="auto",
    )
    return {
        "symbol": symbol,
        "scores": report["scores"],
        "quality_flags": report["quality_flags"],
        "risk_flags": report["risk_flags"],
        "limitations": report["limitations"],
    }


@router.get("/companies/{symbol}/industry-pack")
def get_company_industry_pack(symbol: str, industry: str | None = None) -> dict[str, object]:
    context = type("Context", (), {"industry": industry})()
    selected = IndustryPackRegistry().select(None, context, "auto")
    return {"symbol": symbol, "industry": industry, "selected_packs": selected}


@router.post("/analysis-runs")
def create_analysis_run(payload: dict[str, object]) -> dict[str, object]:
    symbol = payload.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise HTTPException(status_code=400, detail={"code": "symbol_required"})
    as_of_date = payload.get("as_of_date")
    report = _build(
        symbol.strip(),
        as_of_date=as_of_date if isinstance(as_of_date, str) else None,
        strict_as_of=bool(payload.get("strict_as_of", False)),
        include_markdown=bool(payload.get("include_markdown", False)),
        include_evidence=bool(payload.get("include_evidence", True)),
        industry_pack=str(payload.get("industry_pack", "auto")),
    )
    return {
        "status": "completed",
        "symbol": symbol.strip(),
        "analysis_version": report["analysis_version"],
        "generated_at": report["generated_at"],
        "report": report,
    }


def _build(
    symbol: str,
    *,
    as_of_date: str | None,
    strict_as_of: bool,
    include_markdown: bool,
    include_evidence: bool,
    industry_pack: str,
) -> dict[str, object]:
    try:
        return AnalysisService().build(
            symbol,
            as_of_date=as_of_date,
            strict_as_of=strict_as_of,
            include_markdown=include_markdown,
            include_evidence=include_evidence,
            industry_pack=industry_pack,
        ).to_dict()
    except ValueError as exc:
        if str(exc) == "company_not_found":
            raise HTTPException(status_code=404, detail={"code": "company_not_found", "message": f"Company {symbol} is not in the local database."}) from exc
        raise HTTPException(status_code=400, detail={"code": str(exc)}) from exc


def _all_findings(report: dict[str, object]) -> list[object]:
    findings: list[object] = []
    for section_id in (
        "growth",
        "profitability",
        "cash_flow_quality",
        "balance_sheet",
        "efficiency",
        "earnings_quality",
        "industry_specific",
        "market_risk",
        "data_quality",
    ):
        section = report.get(section_id)
        if isinstance(section, dict):
            section_findings = section.get("findings")
            if isinstance(section_findings, list | tuple):
                findings.extend(section_findings)
    return findings
