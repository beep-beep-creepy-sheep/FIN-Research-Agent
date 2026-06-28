from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from finresearch.services.institutional_report import InstitutionalReportService


router = APIRouter()


class ReportRequest(BaseModel):
    as_of_date: str | None = None
    strict_as_of: bool = False
    include_ai: bool = False
    include_markdown: bool = True
    include_html: bool = True
    include_evidence: bool = True
    force_rebuild: bool = False
    sections: list[str] | None = None
    report_style: str = "institutional_full"
    language: str = Field(default="en", pattern="^(en|zh)$")


class RegenerateSectionRequest(BaseModel):
    section_id: str
    include_ai: bool = False


@router.get("/companies/{symbol}/report")
def get_company_report(
    symbol: str,
    as_of_date: str | None = None,
    strict_as_of: bool = False,
    include_ai: bool = False,
    include_markdown: bool = False,
    include_html: bool = False,
    include_evidence: bool = False,
    force_rebuild: bool = False,
    sections: str | None = None,
    report_style: str = "institutional_full",
    language: str = "en",
) -> dict[str, object]:
    request = ReportRequest(
        as_of_date=as_of_date,
        strict_as_of=strict_as_of,
        include_ai=include_ai,
        include_markdown=include_markdown,
        include_html=include_html,
        include_evidence=include_evidence,
        force_rebuild=force_rebuild,
        sections=[item.strip() for item in sections.split(",") if item.strip()] if sections else None,
        report_style=report_style,
        language=language,
    )
    return _build(symbol, request)


@router.post("/companies/{symbol}/report")
def post_company_report(symbol: str, request: ReportRequest) -> dict[str, object]:
    return _build(symbol, request)


@router.get("/companies/{symbol}/report/latest")
def get_latest_company_report(symbol: str) -> dict[str, object]:
    row = InstitutionalReportService().latest(symbol)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "report_run_not_found"})
    return row


@router.get("/companies/{symbol}/report/runs")
def get_company_report_runs(symbol: str) -> list[dict[str, object]]:
    return InstitutionalReportService().runs(symbol)


@router.get("/report-runs/{run_id}")
def get_report_run(run_id: str) -> dict[str, object]:
    row = InstitutionalReportService().get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "report_run_not_found"})
    return row


@router.get("/report-runs/{run_id}/markdown")
def get_report_markdown(run_id: str) -> Response:
    markdown = InstitutionalReportService().markdown(run_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail={"code": "report_run_not_found"})
    return Response(markdown, media_type="text/markdown; charset=utf-8")


@router.get("/report-runs/{run_id}/html")
def get_report_html(run_id: str) -> Response:
    html = InstitutionalReportService().html(run_id)
    if html is None:
        raise HTTPException(status_code=404, detail={"code": "report_run_not_found"})
    return Response(html, media_type="text/html; charset=utf-8")


@router.get("/report-runs/{run_id}/validation")
def get_report_validation(run_id: str) -> dict[str, object]:
    validation = InstitutionalReportService().validation(run_id)
    if validation is None:
        raise HTTPException(status_code=404, detail={"code": "report_run_not_found"})
    return validation


@router.get("/report-runs/{run_id}/evidence")
def get_report_evidence(run_id: str) -> dict[str, object]:
    evidence = InstitutionalReportService().evidence(run_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail={"code": "report_run_not_found"})
    return evidence


@router.post("/report-runs/{run_id}/regenerate-section")
def regenerate_report_section(run_id: str, request: RegenerateSectionRequest) -> dict[str, object]:
    try:
        row = InstitutionalReportService().regenerate_section(
            run_id,
            request.section_id,
            include_ai=request.include_ai,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": str(exc)}) from exc
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "report_run_not_found"})
    return row


def _build(symbol: str, request: ReportRequest) -> dict[str, object]:
    try:
        return InstitutionalReportService().build(
            symbol,
            as_of_date=request.as_of_date,
            strict_as_of=request.strict_as_of,
            include_ai=request.include_ai,
            include_markdown=request.include_markdown,
            include_html=request.include_html,
            include_evidence=request.include_evidence,
            force_rebuild=request.force_rebuild,
            sections=request.sections,
            report_style=request.report_style,
            language=request.language,
        )
    except ValueError as exc:
        code = str(exc)
        status = 404 if code == "company_not_found" else 400
        raise HTTPException(status_code=status, detail={"code": code}) from exc
