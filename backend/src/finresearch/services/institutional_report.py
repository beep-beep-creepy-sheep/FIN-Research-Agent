from __future__ import annotations

import html
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import PurePath
from collections.abc import Callable
from typing import Protocol, cast

from sqlalchemy import select

from finresearch.ai.ollama import OllamaProvider
from finresearch.database.models import AIPromptAudit, Document, DocumentChunk, ReportRun, ReportSection
from finresearch.database.session import session_scope
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.data_quality import DataQualityRepository
from finresearch.repositories.filings import FilingRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.analysis import AnalysisService
from finresearch.services.valuation import PeerMetricsMatrixService, PeerSetService, ValuationLabService
from finresearch.settings import get_settings


REPORT_VERSION = "stage6-report-v1"
GENERATED_BY_DETERMINISTIC = "deterministic_python"
SUPPORTED_LANGUAGES = {"en", "zh"}
SUPPORTED_STYLES = {"institutional_full", "concise_committee_brief", "evidence_appendix_heavy"}
FORBIDDEN_ADVICE_TERMS = ("target price", "买入", "卖出", "持有", "目标价")
WORD_FORBIDDEN_TERMS = ("buy", "sell", "hold")
PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all prior instructions",
    "system prompt",
    "developer message",
    "jailbreak",
    "bypass",
    "override",
    "输出目标价",
    "给出买入",
    "伪造",
)
DEFAULT_SECTIONS = (
    "cover_metadata",
    "executive_summary",
    "company_profile",
    "financial_analysis",
    "industry_pack_analysis",
    "peer_comparison",
    "valuation_lab",
    "risk_data_quality",
    "evidence_appendix",
    "methodology",
    "disclaimers",
)


@dataclass(frozen=True)
class ResearchEvidenceBundle:
    symbol: str
    as_of_date: str
    strict_as_of: bool
    company: dict[str, object] | None
    financial_facts: tuple[dict[str, object], ...]
    prices: tuple[dict[str, object], ...]
    analysis: dict[str, object] | None
    peers: dict[str, object] | None
    peer_metrics: dict[str, object] | None
    valuations: dict[str, object]
    filings: tuple[dict[str, object], ...]
    documents: tuple[dict[str, object], ...]
    evidence_map: tuple[dict[str, object], ...]
    data_quality_issues: tuple[dict[str, object], ...]
    prompt_injection_flags: tuple[dict[str, object], ...]
    limitations: tuple[str, ...]
    bundle_hash: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InstitutionalReportSection:
    section_id: str
    title: str
    status: str
    content: dict[str, object]
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    generated_by: str = GENERATED_BY_DETERMINISTIC
    validation_status: str = "passed"


@dataclass(frozen=True)
class InstitutionalReport:
    run_id: str
    symbol: str
    as_of_date: str
    strict_as_of: bool
    report_style: str
    language: str
    sections: tuple[InstitutionalReportSection, ...]
    validation: dict[str, object]
    evidence_coverage: dict[str, object]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    llm: dict[str, object]
    bundle_hash: str
    report_hash: str
    generated_at: str
    report_version: str = REPORT_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        _guard_no_forbidden_advice(payload)
        return payload


class NarrativeProvider(Protocol):
    def generate(self, prompt: str) -> str: ...


class ResearchEvidenceBundleBuilder:
    def build(self, symbol: str, *, as_of_date: str | None = None, strict_as_of: bool = False) -> ResearchEvidenceBundle:
        effective_as_of = as_of_date or date.today().isoformat()
        company = CompanyRepository().get(symbol)
        if company is None:
            raise ValueError("company_not_found")
        facts = tuple(
            _sanitize_dict(row)
            for row in FinancialFactRepository().list_by_symbol(
                symbol, years=5, as_of_date=effective_as_of, strict_as_of=strict_as_of
            )
        )
        if company is not None:
            company = dict(company)
            company["latest_fact_period"] = max((str(row["period_end"]) for row in facts if row.get("period_end")), default=None)
        prices = tuple(_price_point_dict(point) for point in PriceRepository().price_series(symbol, end_date=effective_as_of, limit=520))
        analysis = _safe_call(
            lambda: AnalysisService()
            .build(symbol, as_of_date=effective_as_of, strict_as_of=strict_as_of, include_markdown=False)
            .to_dict()
        )
        if isinstance(analysis, dict):
            _set_nested_latest_fact_period(analysis, company.get("latest_fact_period") if company else None)
        peers = _safe_call(lambda: PeerSetService().build(symbol, as_of_date=effective_as_of).to_dict())
        peer_symbols = tuple(peers.get("selected_symbols", ())) if isinstance(peers, dict) else ()
        peer_metrics = _safe_call(
            lambda: PeerMetricsMatrixService().build(
                symbol,
                peer_symbols=list(peer_symbols) or None,
                as_of_date=effective_as_of,
                strict_as_of=strict_as_of,
            )
        )
        valuations = {
            "relative_valuation": _safe_call(
                lambda: ValuationLabService().run(
                    symbol,
                    model_type="relative_valuation",
                    as_of_date=effective_as_of,
                    strict_as_of=strict_as_of,
                    peer_symbols=list(peer_symbols) or None,
                )
            ),
            "dcf_owner_earnings": _safe_call(
                lambda: ValuationLabService().run(
                    symbol,
                    model_type="dcf_owner_earnings",
                    as_of_date=effective_as_of,
                    strict_as_of=strict_as_of,
                )
            ),
        }
        filings = tuple(_sanitize_dict(row) for row in FilingRepository().list(symbol, limit=20))
        documents = tuple(_sanitize_dict(row) for row in _documents_for_symbol(symbol, effective_as_of, strict_as_of))
        data_quality = tuple(row for row in DataQualityRepository().list(limit=50) if row.get("symbol") in {None, symbol})
        evidence_map = tuple(
            _build_evidence_map(
                facts=facts,
                prices=prices,
                analysis=analysis if isinstance(analysis, dict) else None,
                filings=filings,
                documents=documents,
                valuations=valuations,
            )
        )
        prompt_flags = tuple(ReportPromptInjectionGuard().scan_documents(documents))
        limitations = tuple(
            _compact_strings(
                [
                    "official_evidence_missing" if not filings else "",
                    "financial_facts_missing" if not facts else "",
                    "local_document_evidence_missing" if not documents else "",
                    "prompt_injection_risk_detected" if prompt_flags else "",
                    *_extract_limitations(analysis),
                    *_extract_limitations(peers),
                    *_extract_limitations(peer_metrics),
                    *_extract_limitations(valuations),
                ]
            )
        )
        stable_payload = _stable_for_hash({
            "symbol": symbol,
            "as_of_date": effective_as_of,
            "strict_as_of": strict_as_of,
            "company": company,
            "financial_facts": facts,
            "prices": prices,
            "analysis": analysis,
            "peers": peers,
            "peer_metrics": peer_metrics,
            "valuations": valuations,
            "filings": filings,
            "documents": documents,
            "evidence_map": evidence_map,
            "data_quality_issues": data_quality,
            "prompt_injection_flags": prompt_flags,
            "limitations": limitations,
        })
        return ResearchEvidenceBundle(
            symbol=symbol,
            as_of_date=effective_as_of,
            strict_as_of=strict_as_of,
            company=company,
            financial_facts=facts,
            prices=prices,
            analysis=analysis if isinstance(analysis, dict) else None,
            peers=peers if isinstance(peers, dict) else None,
            peer_metrics=peer_metrics if isinstance(peer_metrics, dict) else None,
            valuations=valuations,
            filings=filings,
            documents=documents,
            evidence_map=evidence_map,
            data_quality_issues=data_quality,
            prompt_injection_flags=prompt_flags,
            limitations=limitations,
            bundle_hash=_hash(stable_payload),
        )


class ReportPromptInjectionGuard:
    def scan_text(self, text: str) -> list[str]:
        lower = text.lower()
        return [pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern.lower() in lower]

    def scan_documents(self, documents: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
        flags: list[dict[str, object]] = []
        for document in documents:
            text = " ".join(str(document.get(key) or "") for key in ("title", "snippet"))
            matches = self.scan_text(text)
            if matches:
                flags.append(
                    {
                        "document_id": document.get("id"),
                        "title": document.get("title"),
                        "matches": matches,
                        "severity": "high",
                    }
                )
        return flags


class ReportClaimValidator:
    def validate(self, report: InstitutionalReport, bundle: ResearchEvidenceBundle) -> dict[str, object]:
        unsupported: list[str] = []
        warnings: list[str] = []
        evidence_ids = {str(item["evidence_id"]) for item in bundle.evidence_map if item.get("evidence_id")}
        for section in report.sections:
            if section.section_id != "disclaimers" and not section.evidence_ids and section.status == "completed":
                unsupported.append(f"{section.section_id}:missing_evidence_ids")
            for evidence_id in section.evidence_ids:
                if evidence_id not in evidence_ids:
                    unsupported.append(f"{section.section_id}:unknown_evidence_id:{evidence_id}")
            content_text = json.dumps(section.content, ensure_ascii=False).lower()
            if _contains_forbidden_advice(content_text):
                unsupported.append(f"{section.section_id}:forbidden_advice_wording")
            if _contains_local_path(content_text):
                unsupported.append(f"{section.section_id}:local_path_leak")
        if bundle.prompt_injection_flags:
            warnings.append("prompt_injection_risk_detected")
        if not bundle.filings:
            warnings.append("official_evidence_missing")
        if unsupported:
            return {
                "status": "failed",
                "action": "reject_report",
                "unsupported_claims": unsupported,
                "warnings": warnings,
                "validated_at": datetime.now(UTC).isoformat(),
            }
        return {
            "status": "passed",
            "action": "accept",
            "unsupported_claims": [],
            "warnings": warnings,
            "validated_at": datetime.now(UTC).isoformat(),
        }


class DeterministicInstitutionalReportBuilder:
    def build(
        self,
        bundle: ResearchEvidenceBundle,
        *,
        report_style: str = "institutional_full",
        language: str = "en",
        sections: tuple[str, ...] | None = None,
        llm: dict[str, object] | None = None,
    ) -> InstitutionalReport:
        report_style = report_style if report_style in SUPPORTED_STYLES else "institutional_full"
        language = language if language in SUPPORTED_LANGUAGES else "en"
        selected_sections = tuple(section for section in (sections or DEFAULT_SECTIONS) if section in DEFAULT_SECTIONS)
        evidence_ids = tuple(str(item["evidence_id"]) for item in bundle.evidence_map[:12] if item.get("evidence_id"))
        section_builders = {
            "cover_metadata": self._cover,
            "executive_summary": self._summary,
            "company_profile": self._profile,
            "financial_analysis": self._financial,
            "industry_pack_analysis": self._industry,
            "peer_comparison": self._peers,
            "valuation_lab": self._valuation,
            "risk_data_quality": self._risk_quality,
            "evidence_appendix": self._evidence,
            "methodology": self._methodology,
            "disclaimers": self._disclaimers,
        }
        built = tuple(section_builders[section_id](bundle, evidence_ids, language) for section_id in selected_sections)
        temp_hash = _hash(
            {
                "symbol": bundle.symbol,
                "bundle_hash": bundle.bundle_hash,
                "sections": [asdict(section) for section in built],
                "report_style": report_style,
                "language": language,
                "llm": llm or {},
            }
        )
        report = InstitutionalReport(
            run_id=f"report_{temp_hash[:24]}",
            symbol=bundle.symbol,
            as_of_date=bundle.as_of_date,
            strict_as_of=bundle.strict_as_of,
            report_style=report_style,
            language=language,
            sections=built,
            validation={},
            evidence_coverage=_coverage(built, bundle),
            warnings=tuple(bundle.prompt_injection_flags and ("prompt_injection_risk_detected",) or ()),
            limitations=bundle.limitations,
            llm=llm or {"enabled": False, "status": "deterministic_fallback"},
            bundle_hash=bundle.bundle_hash,
            report_hash=temp_hash,
            generated_at=datetime.now(UTC).isoformat(),
        )
        validation = ReportClaimValidator().validate(report, bundle)
        return replace(report, validation=validation)

    def _cover(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        company = bundle.company or {}
        return _section(
            "cover_metadata",
            _title("Cover Metadata", "报告元数据", language),
            {
                "symbol": bundle.symbol,
                "company_name": company.get("company_name") or company.get("name") or bundle.symbol,
                "as_of_date": bundle.as_of_date,
                "strict_as_of": bundle.strict_as_of,
                "currency": company.get("currency"),
                "report_version": REPORT_VERSION,
                "research_use_only": True,
            },
            evidence_ids[:2],
        )

    def _summary(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        facts_count = len(bundle.financial_facts)
        findings = (bundle.analysis or {}).get("key_findings") if bundle.analysis else []
        return _section(
            "executive_summary",
            _title("Executive Summary", "执行摘要", language),
            {
                "summary": _text(
                    f"{bundle.symbol} report uses {facts_count} structured facts, {len(bundle.filings)} filings, and {len(evidence_ids)} evidence references as of {bundle.as_of_date}.",
                    f"{bundle.symbol} 报告基于 {facts_count} 条结构化事实、{len(bundle.filings)} 条公告和 {len(evidence_ids)} 条证据引用，时点为 {bundle.as_of_date}。",
                    language,
                ),
                "top_findings": [_brief_finding(item) for item in findings[:4]] if isinstance(findings, list) else [],
                "data_state": "available" if facts_count else "insufficient_data",
            },
            evidence_ids[:5],
        )

    def _profile(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        company = bundle.company or {}
        return _section(
            "company_profile",
            _title("Company Profile", "公司概况", language),
            {
                "exchange": company.get("exchange"),
                "industry": company.get("industry"),
                "listing_date": company.get("listing_date"),
                "status": company.get("status"),
                "source": "companies",
            },
            evidence_ids[:4],
        )

    def _financial(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        metrics = (bundle.analysis or {}).get("financial_profile", {}) if bundle.analysis else {}
        periods = sorted({str(row.get("period_end")) for row in bundle.financial_facts if row.get("period_end")}, reverse=True)
        return _section(
            "financial_analysis",
            _title("Financial Analysis", "财务分析", language),
            {
                "periods": periods[:5],
                "metric_snapshot": metrics,
                "facts_count": len(bundle.financial_facts),
                "missing_reason": None if bundle.financial_facts else "financial_facts_missing",
            },
            evidence_ids[:8],
            limitations=("financial metrics are deterministic calculations from stored facts",),
        )

    def _industry(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        industry = (bundle.analysis or {}).get("industry_specific", {}) if bundle.analysis else {}
        return _section(
            "industry_pack_analysis",
            _title("Industry Pack Analysis", "行业包分析", language),
            {
                "industry": (bundle.company or {}).get("industry"),
                "section_state": industry.get("state") if isinstance(industry, dict) else "insufficient",
                "findings": industry.get("findings", []) if isinstance(industry, dict) else [],
                "limitations": industry.get("limitations", []) if isinstance(industry, dict) else [],
            },
            evidence_ids[:6],
        )

    def _peers(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        peers = bundle.peers or {}
        matrix = bundle.peer_metrics or {}
        matrix_rows = matrix.get("rows", [])
        return _section(
            "peer_comparison",
            _title("Peer Comparison", "同业比较", language),
            {
                "selected_symbols": peers.get("selected_symbols", []),
                "quality_flags": peers.get("quality_flags", []),
                "matrix_rows": matrix_rows[:8] if isinstance(matrix_rows, list) else [],
                "outlier_policy": matrix.get("outlier_policy"),
            },
            evidence_ids[:8],
            limitations=tuple(_compact_strings(_extract_limitations(peers) + _extract_limitations(matrix))),
        )

    def _valuation(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        return _section(
            "valuation_lab",
            _title("Valuation Lab", "估值实验室", language),
            {
                "models": {
                    key: _valuation_summary(value)
                    for key, value in bundle.valuations.items()
                    if isinstance(value, dict)
                },
                "research_use_only": True,
            },
            evidence_ids[:10],
            limitations=tuple(_compact_strings(_extract_limitations(bundle.valuations))),
        )

    def _risk_quality(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        return _section(
            "risk_data_quality",
            _title("Risk And Data Quality", "风险与数据质量", language),
            {
                "data_quality_issues": bundle.data_quality_issues[:10],
                "prompt_injection_flags": bundle.prompt_injection_flags,
                "limitations": bundle.limitations,
            },
            evidence_ids[:8],
            limitations=bundle.limitations,
        )

    def _evidence(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        return _section(
            "evidence_appendix",
            _title("Evidence Appendix", "证据附录", language),
            {"evidence": bundle.evidence_map, "coverage": {"evidence_count": len(bundle.evidence_map)}},
            tuple(str(item["evidence_id"]) for item in bundle.evidence_map if item.get("evidence_id")),
        )

    def _methodology(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        return _section(
            "methodology",
            _title("Methodology", "方法说明", language),
            {
                "inputs": ["companies", "financial_facts", "prices", "filings", "documents", "analysis", "peers", "valuation_runs"],
                "strict_as_of": bundle.strict_as_of,
                "deterministic_calculation": True,
                "llm_fact_creation_allowed": False,
            },
            evidence_ids[:4],
        )

    def _disclaimers(self, bundle: ResearchEvidenceBundle, evidence_ids: tuple[str, ...], language: str) -> InstitutionalReportSection:
        return _section(
            "disclaimers",
            _title("Disclaimers", "声明", language),
            {
                "research_only": _text(
                    "Not investment advice. The report is for public-information verification and audit trails.",
                    "仅供公开信息核验和审计追踪。",
                    language,
                ),
                "trading_rating": "none",
                "single_point_instruction": "none",
            },
            (),
        )


class AIOrchestrationService:
    def __init__(self, provider: NarrativeProvider | None = None) -> None:
        self.provider = provider

    def maybe_generate(self, bundle: ResearchEvidenceBundle, *, include_ai: bool, language: str) -> tuple[dict[str, object], list[dict[str, object]]]:
        settings = get_settings()
        prompt = _report_prompt(bundle, language)
        audit = {
            "section_id": "executive_summary",
            "prompt_hash": _hash(prompt),
            "response_hash": None,
            "provider": settings.llm_provider,
            "model_name": settings.ollama_model if settings.llm_provider == "ollama" else None,
            "validation_status": "not_used",
            "unsupported_claims": [],
        }
        if not include_ai:
            return {"enabled": False, "status": "disabled_by_request"}, [audit]
        if bundle.prompt_injection_flags:
            audit["validation_status"] = "blocked_prompt_injection"
            return {"enabled": False, "status": "blocked_prompt_injection"}, [audit]
        if not settings.llm_enabled:
            return {"enabled": False, "status": "deterministic_fallback", "reason": "llm_disabled"}, [audit]
        provider = self.provider
        if provider is None and settings.llm_provider == "ollama":
            provider = OllamaProvider(settings)
        if provider is None:
            return {"enabled": False, "status": "deterministic_fallback", "reason": "provider_unavailable"}, [audit]
        try:
            response = provider.generate(prompt)
        except RuntimeError as exc:
            audit["validation_status"] = "provider_error"
            return {"enabled": True, "status": "deterministic_fallback", "reason": str(exc)}, [audit]
        audit["response_hash"] = _hash(response)
        if _contains_forbidden_advice(response) or _contains_local_path(response):
            audit["validation_status"] = "rejected"
            audit["unsupported_claims"] = ["forbidden_or_untrusted_response"]
            return {"enabled": True, "status": "deterministic_fallback", "reason": "validation_rejected"}, [audit]
        audit["validation_status"] = "accepted"
        return {"enabled": True, "status": "accepted", "provider": settings.llm_provider, "model_name": audit["model_name"]}, [audit]


class InstitutionalReportService:
    def __init__(self, ai: AIOrchestrationService | None = None) -> None:
        self.ai = ai or AIOrchestrationService()

    def build(
        self,
        symbol: str,
        *,
        as_of_date: str | None = None,
        strict_as_of: bool = False,
        include_ai: bool = False,
        include_markdown: bool = True,
        include_html: bool = True,
        include_evidence: bool = True,
        force_rebuild: bool = False,
        sections: list[str] | None = None,
        report_style: str = "institutional_full",
        language: str = "en",
    ) -> dict[str, object]:
        bundle = ResearchEvidenceBundleBuilder().build(symbol, as_of_date=as_of_date, strict_as_of=strict_as_of)
        selected_sections = tuple(sections) if sections else None
        llm, audits = self.ai.maybe_generate(bundle, include_ai=include_ai, language=language)
        report = DeterministicInstitutionalReportBuilder().build(
            bundle,
            report_style=report_style,
            language=language,
            sections=selected_sections,
            llm=llm,
        )
        existing = None if force_rebuild else self.get_run(report.run_id)
        if existing is not None:
            return self._shape(existing, include_markdown=include_markdown, include_html=include_html, include_evidence=include_evidence)
        markdown = _to_markdown(report)
        html_text = _to_html(report, markdown)
        payload = report.to_dict()
        with session_scope() as session:
            row = ReportRun(
                run_id=report.run_id,
                symbol=report.symbol,
                as_of_date=report.as_of_date,
                strict_as_of=report.strict_as_of,
                report_style=report.report_style,
                language=report.language,
                bundle_hash=report.bundle_hash,
                report_hash=report.report_hash,
                report_version=REPORT_VERSION,
                status="completed",
                llm_enabled=bool(llm.get("enabled")),
                llm_provider=str(llm.get("provider")) if llm.get("provider") else None,
                model_name=str(llm.get("model_name")) if llm.get("model_name") else None,
                validation_status=str(report.validation.get("status", "unknown")),
                result_json=payload,
                markdown=markdown,
                html=html_text,
                validation_json=report.validation,
                evidence_json=bundle.to_dict() if include_evidence else {"bundle_hash": bundle.bundle_hash},
                limitations_json=list(report.limitations),
            )
            session.add(row)
            session.flush()
            for section in report.sections:
                session.add(
                    ReportSection(
                        report_run_id=row.id,
                        section_id=section.section_id,
                        title=section.title,
                        status=section.status,
                        generated_by=section.generated_by,
                        validation_status=section.validation_status,
                        content_json=section.content,
                        evidence_ids_json=list(section.evidence_ids),
                        limitations_json=list(section.limitations),
                    )
                )
            for audit in audits:
                session.add(
                    AIPromptAudit(
                        report_run_id=row.id,
                        section_id=str(audit.get("section_id")) if audit.get("section_id") else None,
                        prompt_hash=str(audit["prompt_hash"]),
                        response_hash=str(audit.get("response_hash")) if audit.get("response_hash") else None,
                        provider=str(audit.get("provider")) if audit.get("provider") else None,
                        model_name=str(audit.get("model_name")) if audit.get("model_name") else None,
                        validation_status=str(audit.get("validation_status") or "not_used"),
                        unsupported_claims_json=_string_list(audit.get("unsupported_claims")),
                    )
                )
        return self._shape(self.get_run(report.run_id) or payload, include_markdown=include_markdown, include_html=include_html, include_evidence=include_evidence)

    def latest(self, symbol: str) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.scalar(select(ReportRun).where(ReportRun.symbol == symbol).order_by(ReportRun.created_at.desc(), ReportRun.id.desc()))
            return _report_run_dict(row) if row else None

    def runs(self, symbol: str) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(select(ReportRun).where(ReportRun.symbol == symbol).order_by(ReportRun.created_at.desc(), ReportRun.id.desc())).all()
            return [_report_run_summary(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.scalar(select(ReportRun).where(ReportRun.run_id == run_id))
            return _report_run_dict(row) if row else None

    def validation(self, run_id: str) -> dict[str, object] | None:
        row = self.get_run(run_id)
        value = row.get("validation") if row else None
        return value if isinstance(value, dict) else None

    def evidence(self, run_id: str) -> dict[str, object] | None:
        row = self.get_run(run_id)
        value = row.get("evidence") if row else None
        return value if isinstance(value, dict) else None

    def markdown(self, run_id: str) -> str | None:
        row = self.get_run(run_id)
        return str(row.get("markdown") or "") if row else None

    def html(self, run_id: str) -> str | None:
        row = self.get_run(run_id)
        return str(row.get("html") or "") if row else None

    def regenerate_section(self, run_id: str, section_id: str, *, include_ai: bool = False) -> dict[str, object] | None:
        row = self.get_run(run_id)
        if row is None:
            return None
        result = row["report"]
        if not isinstance(result, dict):
            return row
        sections = [item for item in result.get("sections", []) if isinstance(item, dict)]
        known = {item.get("section_id") for item in sections}
        if section_id not in known:
            raise ValueError("report_section_not_found")
        return {"run_id": run_id, "section_id": section_id, "status": "deterministic_section_already_current", "include_ai": include_ai}

    def _shape(self, row: dict[str, object], *, include_markdown: bool, include_html: bool, include_evidence: bool) -> dict[str, object]:
        report = row.get("report", row)
        if not isinstance(report, dict):
            report = {}
        shaped = dict(report)
        shaped["run_id"] = row.get("run_id", shaped.get("run_id"))
        if include_markdown:
            shaped["markdown"] = row.get("markdown")
        if include_html:
            shaped["html"] = row.get("html")
        if include_evidence:
            shaped["evidence"] = row.get("evidence")
        return shaped


def _section(
    section_id: str,
    title: str,
    content: dict[str, object],
    evidence_ids: tuple[str, ...],
    limitations: tuple[str, ...] = (),
) -> InstitutionalReportSection:
    status = "completed" if evidence_ids or section_id == "disclaimers" else "insufficient_data"
    return InstitutionalReportSection(
        section_id=section_id,
        title=title,
        status=status,
        content=content,
        evidence_ids=evidence_ids,
        limitations=limitations,
    )


def _build_evidence_map(
    *,
    facts: tuple[dict[str, object], ...],
    prices: tuple[dict[str, object], ...],
    analysis: dict[str, object] | None,
    filings: tuple[dict[str, object], ...],
    documents: tuple[dict[str, object], ...],
    valuations: dict[str, object],
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    seen: set[str] = set()

    def add(kind: str, source: dict[str, object], note: str | None = None) -> None:
        raw = {"kind": kind, "source": source, "note": note}
        evidence_id = f"ev_{_hash(raw)[:16]}"
        if evidence_id in seen:
            return
        seen.add(evidence_id)
        evidence.append({"evidence_id": evidence_id, "kind": kind, "note": note, **source})

    for row in facts[:80]:
        add(
            "financial_fact",
            {
                "source_fact_ids": [row["id"]] if row.get("id") else [],
                "metric_code": row.get("metric_code"),
                "period_end": row.get("period_end"),
                "publication_date": row.get("publication_date"),
                "unit": row.get("unit"),
                "currency": row.get("currency"),
                "source_urls": [row["source_url"]] if row.get("source_url") else [],
            },
        )
    for row in prices[-20:]:
        add("price", {"source_price_ids": [row["id"]] if row.get("id") else [], "trade_date": row.get("trade_date"), "data_source": row.get("data_source")})
    if analysis:
        analysis_evidence = analysis.get("evidence_map", [])
        if isinstance(analysis_evidence, list):
            for item in analysis_evidence:
                if isinstance(item, dict):
                    add("analysis_evidence", _sanitize_dict(item))
    for filing in filings[:20]:
        add(
            "filing",
            {
                "filing_ids": [filing["id"]] if filing.get("id") else [],
                "title": filing.get("title"),
                "publication_date": filing.get("publication_date"),
                "source_urls": [filing["canonical_url"]] if filing.get("canonical_url") else [],
            },
        )
    for document in documents[:20]:
        add(
            "document",
            {
                "document_ids": [document["id"]] if document.get("id") else [],
                "title": document.get("title"),
                "publication_date": document.get("publication_date"),
                "source_urls": [document["source_url"]] if document.get("source_url") else [],
                "page_number": document.get("page_number"),
            },
        )
    for key, value in valuations.items():
        if isinstance(value, dict):
            add("valuation", {"valuation_run_ids": [value.get("valuation_run_id")], "model_type": key, "evidence": value.get("evidence")})
    return evidence


def _documents_for_symbol(symbol: str, as_of_date: str, strict_as_of: bool) -> list[dict[str, object]]:
    with session_scope() as session:
        statement = select(Document).order_by(Document.publication_date.desc().nullslast(), Document.id.desc()).limit(20)
        rows = session.scalars(statement).all()
        output: list[dict[str, object]] = []
        for row in rows:
            if row.issuer and symbol not in row.issuer and symbol not in row.title:
                continue
            if strict_as_of and row.publication_date and row.publication_date > as_of_date:
                continue
            chunk = session.scalar(select(DocumentChunk).where(DocumentChunk.document_id == row.id).order_by(DocumentChunk.chunk_index).limit(1))
            output.append(
                {
                    "id": row.id,
                    "filing_id": row.filing_id,
                    "title": row.title,
                    "source_url": row.source_url or row.url,
                    "source_type": row.source_type,
                    "issuer": row.issuer,
                    "report_period": row.report_period,
                    "publication_date": row.publication_date,
                    "document_type": row.document_type,
                    "page_number": chunk.page_number if chunk else None,
                    "snippet": (chunk.text[:500] if chunk else None),
                    "content_hash": row.content_hash,
                }
            )
        return output


def _report_run_dict(row: ReportRun) -> dict[str, object]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "symbol": row.symbol,
        "as_of_date": row.as_of_date,
        "strict_as_of": row.strict_as_of,
        "report_style": row.report_style,
        "language": row.language,
        "bundle_hash": row.bundle_hash,
        "report_hash": row.report_hash,
        "report_version": row.report_version,
        "status": row.status,
        "llm_enabled": row.llm_enabled,
        "llm_provider": row.llm_provider,
        "model_name": row.model_name,
        "validation_status": row.validation_status,
        "report": row.result_json,
        "markdown": row.markdown,
        "html": row.html,
        "validation": row.validation_json,
        "evidence": row.evidence_json,
        "limitations": row.limitations_json or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _report_run_summary(row: ReportRun) -> dict[str, object]:
    return {
        "run_id": row.run_id,
        "symbol": row.symbol,
        "as_of_date": row.as_of_date,
        "strict_as_of": row.strict_as_of,
        "report_style": row.report_style,
        "language": row.language,
        "status": row.status,
        "validation_status": row.validation_status,
        "llm_enabled": row.llm_enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _to_markdown(report: InstitutionalReport) -> str:
    lines = [
        f"# Institutional Report: {report.symbol}",
        "",
        "Not investment advice.",
        "",
        f"- As of: {report.as_of_date}",
        f"- Strict as-of: {report.strict_as_of}",
        f"- Validation: {report.validation.get('status')}",
        f"- Evidence coverage: {report.evidence_coverage.get('referenced_evidence_count')}/{report.evidence_coverage.get('available_evidence_count')}",
    ]
    for section in report.sections:
        lines.extend(["", f"## {section.title}", "", json.dumps(section.content, ensure_ascii=False, indent=2, sort_keys=True)])
        if section.limitations:
            lines.extend(["", "Limitations: " + "; ".join(section.limitations)])
    return "\n".join(lines)


def _to_html(report: InstitutionalReport, markdown: str) -> str:
    body = "\n".join(f"<p>{html.escape(line)}</p>" if line else "" for line in markdown.splitlines())
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>"
        f"{html.escape(report.symbol)} Institutional Report</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:900px;margin:32px auto;line-height:1.55;color:#0f172a}"
        "p{margin:0 0 8px} @media print{body{margin:12mm}}</style></head><body>"
        f"{body}</body></html>"
    )


def _coverage(sections: tuple[InstitutionalReportSection, ...], bundle: ResearchEvidenceBundle) -> dict[str, object]:
    referenced = {item for section in sections for item in section.evidence_ids}
    return {
        "available_evidence_count": len(bundle.evidence_map),
        "referenced_evidence_count": len(referenced),
        "sections_with_evidence": sum(1 for section in sections if section.evidence_ids),
        "sections_total": len(sections),
    }


def _report_prompt(bundle: ResearchEvidenceBundle, language: str) -> str:
    return json.dumps(
        {
            "task": "Rewrite only style. Do not add facts, numbers, conclusions, ratings, or source ids.",
            "language": language,
            "bundle_hash": bundle.bundle_hash,
            "allowed_evidence_ids": [item.get("evidence_id") for item in bundle.evidence_map],
            "company": bundle.company,
            "limitations": bundle.limitations,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _valuation_summary(value: dict[str, object]) -> dict[str, object]:
    results = value.get("results")
    return {
        "valuation_run_id": value.get("valuation_run_id"),
        "model_type": value.get("model_type"),
        "scenario_name": value.get("scenario_name"),
        "status": results.get("status") if isinstance(results, dict) else "calculated",
        "limitations": value.get("limitations", []),
        "evidence": value.get("evidence", {}),
    }


def _brief_finding(item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        return {"summary": str(item)}
    return {
        "finding_id": item.get("finding_id"),
        "title": item.get("title"),
        "summary": item.get("summary"),
        "metric_codes": item.get("metric_codes", []),
    }


def _price_point_dict(point: object) -> dict[str, object]:
    return {
        "id": getattr(point, "id", None),
        "symbol": getattr(point, "symbol", None),
        "trade_date": getattr(point, "trade_date", None),
        "close": getattr(point, "close", None),
        "adjustment_type": getattr(point, "adjustment_type", None),
        "data_source": getattr(point, "data_source", None),
    }


def _sanitize_record(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if str(key) in {"local_path", "raw_metadata_path", "source_path", "raw_file_path"}:
                continue
            cleaned[str(key)] = _sanitize_record(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_sanitize_record(item) for item in value]
    if isinstance(value, str) and _looks_like_local_path(value):
        return "[local_path_redacted]"
    return value


def _set_nested_latest_fact_period(value: object, latest_fact_period: object) -> None:
    if isinstance(value, dict):
        if "latest_fact_period" in value:
            value["latest_fact_period"] = latest_fact_period
        for item in value.values():
            _set_nested_latest_fact_period(item, latest_fact_period)
    elif isinstance(value, list):
        for item in value:
            _set_nested_latest_fact_period(item, latest_fact_period)


def _safe_call(func: Callable[[], object]) -> object | None:
    try:
        return _sanitize_record(func())
    except ValueError:
        return None


def _sanitize_dict(value: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], _sanitize_record(value))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _extract_limitations(value: object) -> list[str]:
    limitations: list[str] = []
    if isinstance(value, dict):
        raw = value.get("limitations") or value.get("quality_flags") or []
        if isinstance(raw, list):
            limitations.extend(str(item) for item in raw)
        for item in value.values():
            if isinstance(item, dict | list):
                limitations.extend(_extract_limitations(item))
    elif isinstance(value, list):
        for item in value:
            limitations.extend(_extract_limitations(item))
    return limitations


def _compact_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _title(en: str, zh: str, language: str) -> str:
    return zh if language == "zh" else en


def _text(en: str, zh: str, language: str) -> str:
    return zh if language == "zh" else en


def _hash(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _stable_for_hash(value: object) -> object:
    volatile_keys = {
        "created_at",
        "updated_at",
        "generated_at",
        "retrieved_at",
        "calculated_at",
        "last_seen_at",
        "first_seen_at",
        "valuation_run_id",
    }
    if isinstance(value, dict):
        return {
            str(key): _stable_for_hash(item)
            for key, item in value.items()
            if str(key) not in volatile_keys and not str(key).endswith("_hash")
        }
    if isinstance(value, (list, tuple)):
        return [_stable_for_hash(item) for item in value]
    return value


def _guard_no_forbidden_advice(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    if _contains_forbidden_advice(text):
        raise ValueError("forbidden_report_advice_wording")


def _contains_forbidden_advice(text: str) -> bool:
    lower = text.lower()
    if any(term in lower for term in FORBIDDEN_ADVICE_TERMS):
        return True
    return any(re.search(rf"\b{term}\b", lower) for term in WORD_FORBIDDEN_TERMS)


def _contains_local_path(text: str) -> bool:
    return _looks_like_local_path(text)


def _looks_like_local_path(value: str) -> bool:
    if value.startswith(("/", "file://")):
        return True
    try:
        path = PurePath(value)
    except ValueError:
        return False
    return path.is_absolute() or bool(re.search(r"[A-Za-z]:\\", value))
