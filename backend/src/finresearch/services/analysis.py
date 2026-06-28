from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import PurePath
from typing import Protocol

from finresearch.metrics.context import CalculationContext, MetricResult
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.data_quality import DataQualityRepository
from finresearch.repositories.filings import FilingRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.metric_calculation import MetricCalculationService


ANALYSIS_VERSION = "4.0.0"
GENERATED_BY = "deterministic_python"
INVESTMENT_ADVICE_TERMS = ("buy", "sell", "hold", "target price", "买入", "卖出", "持有", "目标价")


@dataclass(frozen=True)
class EvidenceReference:
    reference_id: str
    kind: str
    metric_code: str | None = None
    source_fact_ids: tuple[int, ...] = ()
    source_price_ids: tuple[int, ...] = ()
    filing_ids: tuple[int, ...] = ()
    document_ids: tuple[int, ...] = ()
    citation_ids: tuple[int, ...] = ()
    source_urls: tuple[str, ...] = ()
    page_number: int | None = None
    note: str | None = None


@dataclass(frozen=True)
class AnalysisFinding:
    finding_id: str
    category: str
    title: str
    severity: str
    direction: str
    summary: str
    metric_codes: tuple[str, ...] = ()
    values_used: dict[str, object] = field(default_factory=dict)
    period_range: dict[str, str | None] = field(default_factory=dict)
    source_fact_ids: tuple[int, ...] = ()
    source_price_ids: tuple[int, ...] = ()
    filing_ids: tuple[int, ...] = ()
    document_ids: tuple[int, ...] = ()
    citation_ids: tuple[int, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    confidence: str = "medium"
    generated_by: str = GENERATED_BY
    analysis_version: str = ANALYSIS_VERSION


@dataclass(frozen=True)
class AnalysisSection:
    section_id: str
    title: str
    state: str
    score: float | None = None
    qualitative_state: str | None = None
    findings: tuple[AnalysisFinding, ...] = ()
    supporting_metrics: tuple[str, ...] = ()
    missing_data_warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoreComponent:
    component_id: str
    score: float | None
    reason: str
    metric_codes: tuple[str, ...] = ()
    caveat: str = "Research-quality score only; not an investment recommendation."


@dataclass(frozen=True)
class AnalysisScore:
    score_id: str
    score: float | None
    status: str
    components: tuple[ScoreComponent, ...]
    caveat: str = "Score explains evidence coverage and deterministic risk flags; it is not a trading signal."


@dataclass(frozen=True)
class AnalysisQualityFlag:
    flag_id: str
    severity: str
    message: str
    missing_reason: str | None = None


@dataclass(frozen=True)
class AnalysisRiskFlag:
    flag_id: str
    severity: str
    message: str
    metric_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisContext:
    symbol: str
    company: dict[str, object] | None
    industry: str | None
    exchange: str | None
    currency: str | None
    as_of_date: str
    financial_periods: tuple[str, ...]
    metric_observations: tuple[MetricResult, ...]
    price_analytics: tuple[MetricResult, ...]
    benchmark_selection: dict[str, object] | None
    filings: tuple[dict[str, object], ...]
    documents: tuple[dict[str, object], ...]
    citations: tuple[dict[str, object], ...]
    data_quality_issues: tuple[dict[str, object], ...]
    source_lineage: dict[str, object]
    strict_as_of: bool
    analysis_version: str = ANALYSIS_VERSION


@dataclass(frozen=True)
class AnalysisReport:
    symbol: str
    executive_summary: str
    key_findings: tuple[AnalysisFinding, ...]
    financial_profile: dict[str, object]
    growth: AnalysisSection
    profitability: AnalysisSection
    cash_flow_quality: AnalysisSection
    balance_sheet: AnalysisSection
    efficiency: AnalysisSection
    earnings_quality: AnalysisSection
    industry_specific: AnalysisSection
    market_risk: AnalysisSection
    data_quality: AnalysisSection
    evidence_map: tuple[EvidenceReference, ...]
    scores: tuple[AnalysisScore, ...]
    quality_flags: tuple[AnalysisQualityFlag, ...]
    risk_flags: tuple[AnalysisRiskFlag, ...]
    limitations: tuple[str, ...]
    context: AnalysisContext
    markdown: str | None
    generated_at: str
    analysis_version: str = ANALYSIS_VERSION

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        _guard_no_advice(payload)
        return payload


class IndustryAnalysisPack(Protocol):
    pack_id: str

    def supports(self, company: dict[str, object] | None, context: AnalysisContext) -> bool: ...

    def required_metrics(self) -> tuple[str, ...]: ...

    def data_requirements(self) -> tuple[str, ...]: ...

    def missing_behavior(self) -> str: ...

    def industry_specific_flags(self, context: AnalysisContext) -> tuple[AnalysisRiskFlag, ...]: ...

    def analyze(self, context: AnalysisContext) -> AnalysisSection: ...


class AnalysisService:
    def build(
        self,
        symbol: str,
        *,
        as_of_date: str | None = None,
        strict_as_of: bool = False,
        include_markdown: bool = False,
        include_evidence: bool = True,
        industry_pack: str = "auto",
    ) -> AnalysisReport:
        company = CompanyRepository().get(symbol)
        if company is None:
            raise ValueError("company_not_found")
        effective_as_of = as_of_date or date.today().isoformat()
        periods = tuple(
            FinancialFactRepository().periods(
                symbol,
                years=None,
                as_of_date=effective_as_of,
                strict_as_of=strict_as_of,
            )
        )
        prices = tuple(PriceRepository().price_series(symbol, end_date=effective_as_of, limit=520))
        currency = next((period.currency for period in periods if period.currency), company.get("currency"))
        calc_context = CalculationContext(
            financial_periods=periods,
            price_series=prices,
            as_of_date=effective_as_of,
            strict_as_of=strict_as_of,
            currency=str(currency) if currency else None,
            industry=_str_or_none(company.get("industry")),
        )
        metrics = tuple(MetricCalculationService().calculate(calc_context, symbol=symbol))
        filings = tuple(_safe_filing(row) for row in FilingRepository().list(symbol, limit=20))
        data_quality = tuple(DataQualityRepository().list(limit=50))
        context = AnalysisContext(
            symbol=symbol,
            company=company,
            industry=_str_or_none(company.get("industry")),
            exchange=_str_or_none(company.get("exchange")),
            currency=str(currency) if currency else None,
            as_of_date=effective_as_of,
            financial_periods=tuple(period.period_end for period in periods),
            metric_observations=metrics,
            price_analytics=tuple(metric for metric in metrics if metric.code in MARKET_RISK_METRICS),
            benchmark_selection=None,
            filings=filings,
            documents=(),
            citations=(),
            data_quality_issues=data_quality,
            source_lineage=_source_lineage(metrics, filings),
            strict_as_of=strict_as_of,
        )
        report = AnalysisReportBuilder().build(
            context,
            requested_pack=industry_pack,
            include_markdown=include_markdown,
            include_evidence=include_evidence,
        )
        return report


class GeneralCompanyAnalysisPack:
    pack_id = "general"

    def supports(self, company: dict[str, object] | None, context: AnalysisContext) -> bool:
        return True

    def required_metrics(self) -> tuple[str, ...]:
        return (
            "revenue_yoy",
            "net_profit_yoy",
            "gross_margin",
            "operating_margin",
            "net_margin",
            "roe",
            "roa",
            "roic",
            "fcf_ttm",
            "current_ratio",
            "debt_to_assets",
            "inventory_turnover",
            "receivables_turnover",
            "cash_conversion_cycle",
            "annualized_volatility",
            "max_drawdown",
            "beta",
            "alpha",
            "information_ratio",
        )

    def data_requirements(self) -> tuple[str, ...]:
        return ("structured financial facts", "price series", "official filings or issuer source URLs")

    def missing_behavior(self) -> str:
        return "Return missing/insufficient findings with metric-level missing reasons."

    def industry_specific_flags(self, context: AnalysisContext) -> tuple[AnalysisRiskFlag, ...]:
        return ()

    def analyze(self, context: AnalysisContext) -> AnalysisSection:
        raise NotImplementedError("General pack is expanded by AnalysisReportBuilder sections.")


class BankAnalysisPack:
    pack_id = "bank"

    def supports(self, company: dict[str, object] | None, context: AnalysisContext) -> bool:
        return _is_bank(context.industry)

    def required_metrics(self) -> tuple[str, ...]:
        return (
            "roe",
            "roa",
            "net_interest_margin",
            "cost_income_ratio",
            "fee_income_ratio",
            "non_performing_loan_ratio",
            "provision_coverage_ratio",
            "capital_adequacy_ratio",
            "tier1_capital_ratio",
            "loan_deposit_ratio",
        )

    def data_requirements(self) -> tuple[str, ...]:
        return ("bank regulatory ratios", "balance sheet structure", "official filing evidence")

    def missing_behavior(self) -> str:
        return "Bank-only unavailable ratios remain missing; industrial metrics are not applied."

    def industry_specific_flags(self, context: AnalysisContext) -> tuple[AnalysisRiskFlag, ...]:
        metrics = _metrics_by_code(context.metric_observations)
        flags: list[AnalysisRiskFlag] = []
        if not any(code in metrics and metrics[code].value is not None for code in self.required_metrics()[2:]):
            flags.append(
                AnalysisRiskFlag(
                    "missing_bank_regulatory_ratios",
                    "medium",
                    "Bank regulatory ratios are unavailable, so bank-specific risk analysis is insufficient.",
                    self.required_metrics()[2:],
                )
            )
        return tuple(flags)

    def analyze(self, context: AnalysisContext) -> AnalysisSection:
        findings = [
            _finding_from_metric(
                context,
                "bank_profitability",
                ("roe", "roa", "net_interest_margin", "cost_income_ratio", "fee_income_ratio"),
                "Bank profitability coverage",
            ),
            _finding_from_metric(
                context,
                "bank_asset_quality",
                ("non_performing_loan_ratio", "provision_coverage_ratio", "credit_cost"),
                "Bank asset-quality coverage",
            ),
            _finding_from_metric(
                context,
                "bank_capital",
                ("capital_adequacy_ratio", "tier1_capital_ratio", "core_tier1_ratio"),
                "Bank capital adequacy coverage",
            ),
        ]
        return _section(
            "industry_bank",
            "Bank Industry Pack",
            tuple(findings),
            self.required_metrics(),
            ("Industrial gross-margin, inventory-turnover, and current-ratio conclusions are not applied to banks.",),
        )


class ConsumerManufacturingAnalysisPack:
    pack_id = "consumer_manufacturing"

    def supports(self, company: dict[str, object] | None, context: AnalysisContext) -> bool:
        return _is_consumer_or_manufacturing(context.industry)

    def required_metrics(self) -> tuple[str, ...]:
        return (
            "revenue_yoy",
            "gross_margin",
            "operating_margin",
            "net_margin",
            "roic",
            "inventory_turnover",
            "receivables_turnover",
            "payables_turnover",
            "cash_conversion_cycle",
            "fcf_ttm",
        )

    def data_requirements(self) -> tuple[str, ...]:
        return ("revenue and margins", "working-capital metrics", "capex and cash-flow facts")

    def missing_behavior(self) -> str:
        return "Return proxy findings only when deterministic metrics exist; otherwise insufficient_industry_data."

    def industry_specific_flags(self, context: AnalysisContext) -> tuple[AnalysisRiskFlag, ...]:
        metrics = _metrics_by_code(context.metric_observations)
        flags: list[AnalysisRiskFlag] = []
        revenue = _value(metrics.get("revenue_yoy"))
        fcf = _value(metrics.get("fcf_ttm"))
        net_profit = _value(metrics.get("net_profit_ttm"))
        if fcf is not None and net_profit is not None and net_profit > 0 and fcf < net_profit * 0.5:
            flags.append(
                AnalysisRiskFlag(
                    "cash_flow_weaker_than_profit",
                    "medium",
                    "Free cash flow is materially weaker than reported profit.",
                    ("fcf_ttm", "net_profit_ttm"),
                )
            )
        if revenue is not None and revenue < 0:
            flags.append(
                AnalysisRiskFlag(
                    "revenue_slowdown",
                    "low",
                    "Revenue growth is negative in the selected period.",
                    ("revenue_yoy",),
                )
            )
        return tuple(flags)

    def analyze(self, context: AnalysisContext) -> AnalysisSection:
        findings = [
            _finding_from_metric(context, "demand", ("revenue_yoy",), "Revenue and demand proxy"),
            _finding_from_metric(context, "margin_structure", ("gross_margin", "operating_margin", "net_margin"), "Margin structure"),
            _finding_from_metric(
                context,
                "working_capital",
                ("inventory_turnover", "receivables_turnover", "payables_turnover", "cash_conversion_cycle"),
                "Working-capital profile",
            ),
            _finding_from_metric(context, "pricing_power_proxy", ("gross_margin", "roic", "fcf_ttm"), "Brand/pricing-power proxy"),
        ]
        return _section(
            "industry_consumer_manufacturing",
            "Consumer / Manufacturing Pack",
            tuple(findings),
            self.required_metrics(),
            ("This is a proxy analysis; it does not claim brand strength without direct evidence.",),
        )


class IndustryPackRegistry:
    def __init__(self) -> None:
        self.general = GeneralCompanyAnalysisPack()
        self.bank = BankAnalysisPack()
        self.consumer_manufacturing = ConsumerManufacturingAnalysisPack()

    def select(self, company: dict[str, object] | None, context: AnalysisContext, requested: str = "auto") -> tuple[str, ...]:
        if requested == "general":
            return ("general",)
        if requested == "bank":
            return ("general", "bank")
        if requested in {"consumer_manufacturing", "consumer_or_manufacturing"}:
            return ("general", "consumer_manufacturing")
        if requested != "auto":
            return ("general",)
        if self.bank.supports(company, context):
            return ("general", "bank")
        if self.consumer_manufacturing.supports(company, context):
            return ("general", "consumer_manufacturing")
        return ("general",)

    def get(self, pack_id: str) -> IndustryAnalysisPack:
        if pack_id == "bank":
            return self.bank
        if pack_id == "consumer_manufacturing":
            return self.consumer_manufacturing
        return self.general


class AnalysisScoringService:
    def score(self, context: AnalysisContext, sections: tuple[AnalysisSection, ...]) -> tuple[AnalysisScore, ...]:
        scores = [
            self._section_score("growth_score", _find_section(sections, "growth")),
            self._section_score("profitability_score", _find_section(sections, "profitability")),
            self._section_score("cash_flow_quality_score", _find_section(sections, "cash_flow_quality")),
            self._section_score("balance_sheet_score", _find_section(sections, "balance_sheet")),
            self._section_score("efficiency_score", _find_section(sections, "efficiency")),
            self._section_score("earnings_quality_score", _find_section(sections, "earnings_quality")),
            self._section_score("market_risk_score", _find_section(sections, "market_risk")),
            self._data_quality_score(context),
        ]
        available = [score.score for score in scores if score.score is not None]
        overall = AnalysisScore(
            "overall_research_quality_score",
            round(sum(available) / len(available), 2) if available else None,
            "calculated" if available else "insufficient_data",
            tuple(
                ScoreComponent(score.score_id, score.score, score.status)
                for score in scores
            ),
        )
        scores.append(overall)
        return tuple(scores)

    def _section_score(self, score_id: str, section: AnalysisSection | None) -> AnalysisScore:
        if section is None or not section.findings:
            return AnalysisScore(score_id, None, "insufficient_data", (ScoreComponent("coverage", None, "No section findings."),))
        calculated = [finding for finding in section.findings if finding.direction != "missing"]
        missing = [finding for finding in section.findings if finding.direction == "missing"]
        score = max(0.0, round(100.0 * len(calculated) / len(section.findings) - 10.0 * len(missing), 2))
        return AnalysisScore(
            score_id,
            score,
            "calculated" if calculated else "insufficient_data",
            (
                ScoreComponent("calculated_findings", float(len(calculated)), "Findings with deterministic metric values.", section.supporting_metrics),
                ScoreComponent("missing_findings", float(len(missing)), "Missing inputs reduce the score.", section.supporting_metrics),
            ),
        )

    def _data_quality_score(self, context: AnalysisContext) -> AnalysisScore:
        issue_count = len(context.data_quality_issues)
        has_official = any(filing.get("source_tier") in {"official", "regulator", "exchange", "issuer"} for filing in context.filings)
        base = 100.0 - issue_count * 10.0 - (0.0 if has_official else 20.0)
        return AnalysisScore(
            "data_quality_score",
            max(0.0, base),
            "calculated",
            (
                ScoreComponent("open_data_quality_issues", float(issue_count), "Open data-quality issues lower research quality."),
                ScoreComponent(
                    "official_filing_coverage",
                    1.0 if has_official else 0.0,
                    "Official filing evidence is present." if has_official else "No official filing evidence is available.",
                ),
            ),
        )


class AnalysisReportBuilder:
    def build(
        self,
        context: AnalysisContext,
        *,
        requested_pack: str,
        include_markdown: bool,
        include_evidence: bool,
    ) -> AnalysisReport:
        registry = IndustryPackRegistry()
        selected_pack_ids = registry.select(context.company, context, requested_pack)
        growth = _analysis_section(context, "growth", "Growth Analysis", ("revenue_yoy", "net_profit_yoy", "operating_cash_flow_yoy"))
        profitability = _analysis_section(
            context,
            "profitability",
            "Profitability Analysis",
            ("gross_margin", "operating_margin", "net_margin", "roe", "roa", "roic"),
        )
        cash_flow = _analysis_section(
            context,
            "cash_flow_quality",
            "Cash Flow Quality",
            ("operating_cash_flow", "fcf_ttm", "fcf_yield", "cash_conversion"),
        )
        balance = _analysis_section(
            context,
            "balance_sheet",
            "Balance Sheet Strength",
            ("current_ratio", "quick_ratio", "debt_to_assets", "net_debt", "interest_coverage"),
        )
        efficiency = _analysis_section(
            context,
            "efficiency",
            "Efficiency Analysis",
            ("inventory_turnover", "receivables_turnover", "payables_turnover", "cash_conversion_cycle", "asset_turnover"),
        )
        earnings = _analysis_section(
            context,
            "earnings_quality",
            "Earnings Quality",
            ("net_profit_ttm", "fcf_ttm", "receivables_turnover", "inventory_turnover"),
        )
        market = _analysis_section(
            context,
            "market_risk",
            "Market Risk Snapshot",
            ("annualized_volatility", "max_drawdown", "beta", "alpha", "information_ratio"),
        )
        data_quality = _data_quality_section(context)
        industry = self._industry_section(context, registry, selected_pack_ids)
        sections = (growth, profitability, cash_flow, balance, efficiency, earnings, industry, market, data_quality)
        scores = AnalysisScoringService().score(context, sections)
        findings = tuple(finding for section in sections for finding in section.findings)
        evidence = tuple(reference for finding in findings for reference in finding.evidence) if include_evidence else ()
        quality_flags = _quality_flags(context)
        risk_flags = tuple(flag for pack_id in selected_pack_ids for flag in registry.get(pack_id).industry_specific_flags(context))
        limitations = _limitations(context, selected_pack_ids)
        summary = _executive_summary(context, findings, selected_pack_ids)
        report = AnalysisReport(
            symbol=context.symbol,
            executive_summary=summary,
            key_findings=findings[:8],
            financial_profile={
                "industry": context.industry or "unknown",
                "exchange": context.exchange,
                "currency": context.currency,
                "industry_packs": selected_pack_ids,
                "strict_as_of": context.strict_as_of,
            },
            growth=growth,
            profitability=profitability,
            cash_flow_quality=cash_flow,
            balance_sheet=balance,
            efficiency=efficiency,
            earnings_quality=earnings,
            industry_specific=industry,
            market_risk=market,
            data_quality=data_quality,
            evidence_map=evidence,
            scores=scores,
            quality_flags=quality_flags,
            risk_flags=risk_flags,
            limitations=limitations,
            context=context,
            markdown=None,
            generated_at=datetime.now(UTC).isoformat(),
        )
        markdown = render_markdown(report) if include_markdown else None
        return replace(report, markdown=markdown)

    def _industry_section(
        self,
        context: AnalysisContext,
        registry: IndustryPackRegistry,
        selected_pack_ids: tuple[str, ...],
    ) -> AnalysisSection:
        industry_pack_ids = tuple(pack_id for pack_id in selected_pack_ids if pack_id != "general")
        if not industry_pack_ids:
            return AnalysisSection(
                "industry_specific",
                "Industry Pack",
                "insufficient",
                qualitative_state="industry_unknown_general_only" if not context.industry else "general_only",
                findings=(
                    AnalysisFinding(
                        "industry_unknown",
                        "industry_specific",
                        "Industry-specific pack not selected",
                        "low",
                        "missing",
                        "Industry is unknown or not mapped, so only the general pack is used.",
                        limitations=("Industry cannot be guessed from ticker alone.",),
                    ),
                ),
                missing_data_warnings=("industry_unknown" if not context.industry else "unsupported_industry",),
            )
        return registry.get(industry_pack_ids[0]).analyze(context)


def render_markdown(report: AnalysisReport) -> str:
    lines = [
        f"# Professional Analysis: {report.symbol}",
        "",
        report.executive_summary,
        "",
        "This report is deterministic research output, not investment advice.",
        "",
        "## Key Findings",
    ]
    for finding in report.key_findings:
        marker = _evidence_marker(finding)
        lines.append(f"- {finding.title}: {finding.summary} {marker}")
    lines.extend(["", "## Scores"])
    for score in report.scores:
        value = "insufficient_data" if score.score is None else f"{score.score:.2f}"
        lines.append(f"- {score.score_id}: {value} ({score.status})")
    lines.extend(["", "## Limitations"])
    for limitation in report.limitations:
        lines.append(f"- {limitation}")
    markdown = "\n".join(lines)
    _guard_no_advice(markdown)
    return markdown


def _analysis_section(
    context: AnalysisContext,
    section_id: str,
    title: str,
    metric_codes: tuple[str, ...],
) -> AnalysisSection:
    findings = tuple(
        _finding_from_metric(context, f"{section_id}_{code}", (code,), f"{title}: {code}")
        for code in metric_codes
    )
    return _section(section_id, title, findings, metric_codes)


def _data_quality_section(context: AnalysisContext) -> AnalysisSection:
    findings: list[AnalysisFinding] = []
    if not context.filings:
        findings.append(
            AnalysisFinding(
                "official_filing_missing",
                "data_quality",
                "Official filing evidence missing",
                "medium",
                "missing",
                "No official filing metadata is available for this company in the local database.",
                limitations=("Run official filing sync to improve evidence coverage.",),
            )
        )
    for issue in context.data_quality_issues[:5]:
        findings.append(
            AnalysisFinding(
                f"data_quality_issue_{issue.get('id', len(findings))}",
                "data_quality",
                str(issue.get("issue_type", "data quality issue")),
                str(issue.get("severity", "medium")),
                "negative",
                str(issue.get("description") or issue.get("message") or "Data quality issue is open."),
                limitations=(str(issue.get("status", "open")),),
            )
        )
    if not findings:
        findings.append(
            AnalysisFinding(
                "data_quality_no_open_issues",
                "data_quality",
                "No open data-quality issues found",
                "low",
                "neutral",
                "The local data-quality issue table has no open issues for the checked set.",
                assumptions=("Absence of an issue does not prove complete data coverage.",),
            )
        )
    return _section("data_quality", "Data Quality and Evidence", tuple(findings), ())


def _section(
    section_id: str,
    title: str,
    findings: tuple[AnalysisFinding, ...],
    supporting_metrics: tuple[str, ...],
    limitations: tuple[str, ...] = (),
) -> AnalysisSection:
    calculated = [finding for finding in findings if finding.direction != "missing"]
    state = "calculated" if calculated else "insufficient"
    return AnalysisSection(
        section_id,
        title,
        state,
        qualitative_state="mixed" if calculated and len(calculated) < len(findings) else state,
        findings=findings,
        supporting_metrics=supporting_metrics,
        missing_data_warnings=tuple(
            str(finding.values_used.get("missing_reason"))
            for finding in findings
            if finding.direction == "missing" and finding.values_used.get("missing_reason")
        ),
        limitations=limitations,
    )


def _finding_from_metric(
    context: AnalysisContext,
    suffix: str,
    metric_codes: tuple[str, ...],
    title: str,
) -> AnalysisFinding:
    metrics = _metrics_by_code(context.metric_observations)
    present = [metrics[code] for code in metric_codes if code in metrics and metrics[code].value is not None]
    missing = [metrics[code] for code in metric_codes if code in metrics and metrics[code].value is None]
    if not present:
        reason = missing[0].missing_reason if missing else "metric_not_available"
        return AnalysisFinding(
            f"{context.symbol}_{suffix}",
            suffix.split("_", 1)[0],
            title,
            "medium",
            "missing",
            f"Insufficient deterministic data for {', '.join(metric_codes)}.",
            metric_codes=metric_codes,
            values_used={"missing_reason": reason},
            limitations=("Missing data is reported explicitly; no values were inferred.",),
            confidence="low",
        )
    fact_ids = tuple(dict.fromkeys(fact_id for metric in present for fact_id in metric.source_fact_ids))
    price_ids = tuple(dict.fromkeys(price_id for metric in present for price_id in metric.source_price_ids))
    evidence = tuple(_metric_evidence(metric) for metric in present)
    values = {metric.code: metric.value for metric in present}
    directions = [_direction(metric.value) for metric in present if metric.value is not None]
    direction = "neutral" if "negative" not in directions and "positive" not in directions else ("negative" if "negative" in directions else "positive")
    first = present[0]
    return AnalysisFinding(
        f"{context.symbol}_{suffix}",
        suffix.split("_", 1)[0],
        title,
        "low" if direction != "negative" else "medium",
        direction,
        f"Calculated from deterministic metrics: {', '.join(f'{code}={values[code]}' for code in values)}.",
        metric_codes=tuple(metric.code for metric in present),
        values_used=values,
        period_range={"start": first.period_start, "end": first.period_end, "as_of": first.as_of or context.as_of_date},
        source_fact_ids=fact_ids,
        source_price_ids=price_ids,
        evidence=evidence,
        assumptions=tuple(
            f"{key}={value}"
            for metric in present
            for key, value in metric.assumptions.items()
        ),
        limitations=tuple(dict.fromkeys(warning for metric in present for warning in metric.warnings)),
        confidence="high" if fact_ids or price_ids else "medium",
    )


def _metric_evidence(metric: MetricResult) -> EvidenceReference:
    return EvidenceReference(
        reference_id=f"metric:{metric.code}",
        kind="metric",
        metric_code=metric.code,
        source_fact_ids=metric.source_fact_ids,
        source_price_ids=metric.source_price_ids,
        source_urls=tuple(_safe_url(url) for url in metric.source_urls),
        note=metric.formula,
    )


def _metrics_by_code(metrics: tuple[MetricResult, ...]) -> dict[str, MetricResult]:
    return {metric.code: metric for metric in metrics}


def _value(metric: MetricResult | None) -> float | None:
    return metric.value if metric is not None else None


def _direction(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 0:
        return "negative"
    if value > 0:
        return "positive"
    return "neutral"


def _source_lineage(metrics: tuple[MetricResult, ...], filings: tuple[dict[str, object], ...]) -> dict[str, object]:
    return {
        "metric_codes": [metric.code for metric in metrics],
        "source_fact_ids": sorted({fact_id for metric in metrics for fact_id in metric.source_fact_ids}),
        "source_price_ids": sorted({price_id for metric in metrics for price_id in metric.source_price_ids}),
        "filing_ids": [filing.get("id") for filing in filings if filing.get("id") is not None],
    }


def _quality_flags(context: AnalysisContext) -> tuple[AnalysisQualityFlag, ...]:
    flags: list[AnalysisQualityFlag] = []
    if not context.filings:
        flags.append(AnalysisQualityFlag("missing_official_filing", "medium", "Official filing metadata is missing.", "official_filing_missing"))
    missing_metrics = [metric for metric in context.metric_observations if metric.value is None]
    if missing_metrics:
        flags.append(
            AnalysisQualityFlag(
                "missing_metrics",
                "low",
                f"{len(missing_metrics)} metric observations are missing or not applicable.",
                "metric_inputs_missing",
            )
        )
    if any(metric.code in {"beta", "alpha", "information_ratio"} and metric.value is None for metric in context.metric_observations):
        flags.append(AnalysisQualityFlag("benchmark_missing", "low", "Benchmark-dependent market risk metrics are unavailable.", "benchmark_missing"))
    return tuple(flags)


def _limitations(context: AnalysisContext, pack_ids: tuple[str, ...]) -> tuple[str, ...]:
    items = [
        "Deterministic analysis only; AI is not used to create financial facts.",
        "Scores are research-quality and risk-flag summaries, not investment advice.",
    ]
    if context.strict_as_of:
        items.append(f"strict_as_of is enabled; facts published after {context.as_of_date} are excluded.")
    if "bank" in pack_ids:
        items.append("Bank pack avoids industrial metrics that are not applicable to banks.")
    if not context.filings:
        items.append("Official filing evidence is missing in local storage.")
    return tuple(items)


def _executive_summary(context: AnalysisContext, findings: tuple[AnalysisFinding, ...], pack_ids: tuple[str, ...]) -> str:
    calculated = sum(1 for finding in findings if finding.direction != "missing")
    missing = sum(1 for finding in findings if finding.direction == "missing")
    return (
        f"{context.symbol} analysis used packs {', '.join(pack_ids)} with {calculated} deterministic findings "
        f"and {missing} explicit missing-data findings as of {context.as_of_date}."
    )


def _evidence_marker(finding: AnalysisFinding) -> str:
    parts: list[str] = []
    if finding.source_fact_ids:
        parts.append(f"facts={','.join(str(item) for item in finding.source_fact_ids)}")
    if finding.source_price_ids:
        parts.append(f"prices={','.join(str(item) for item in finding.source_price_ids)}")
    if finding.filing_ids:
        parts.append(f"filings={','.join(str(item) for item in finding.filing_ids)}")
    return f"[evidence:{';'.join(parts)}]" if parts else "[evidence:missing]"


def _is_bank(industry: str | None) -> bool:
    text = (industry or "").lower()
    return any(token in text for token in ("bank", "银行"))


def _is_consumer_or_manufacturing(industry: str | None) -> bool:
    text = (industry or "").lower()
    return any(token in text for token in ("consumer", "manufact", "制造", "消费", "食品", "饮料"))


def _find_section(sections: tuple[AnalysisSection, ...], section_id: str) -> AnalysisSection | None:
    return next((section for section in sections if section.section_id == section_id), None)


def _safe_filing(row: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"local_path", "raw_metadata_path"} and not _looks_like_local_path(value)
    }


def _safe_url(value: str) -> str:
    return "" if _looks_like_local_path(value) else value


def _looks_like_local_path(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if value.startswith(("/", "file:")):
        return True
    try:
        return bool(PurePath(value).is_absolute())
    except ValueError:
        return False


def _str_or_none(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _guard_no_advice(payload: object) -> None:
    text = str(payload).lower()
    if any(term.lower() in text for term in INVESTMENT_ADVICE_TERMS):
        raise ValueError("analysis_output_contains_investment_advice_language")


MARKET_RISK_METRICS = frozenset({"annualized_volatility", "max_drawdown", "beta", "alpha", "information_ratio"})
