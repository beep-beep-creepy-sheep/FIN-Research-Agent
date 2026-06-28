from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from statistics import fmean, median, pstdev
from typing import cast

from sqlalchemy import select

from finresearch.database.models import Company, PeerSet, PeerSetMember, ValuationAssumption, ValuationRun
from finresearch.database.session import session_scope
from finresearch.metrics.context import CalculationContext, MetricResult
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.analysis import INVESTMENT_ADVICE_TERMS
from finresearch.services.metric_calculation import MetricCalculationService


VALUATION_VERSION = "stage5-valuation-v1"
PEER_VERSION = "stage5-peer-v1"
DEFAULT_PEER_METRICS = (
    "revenue_ttm",
    "net_profit_ttm",
    "revenue_growth",
    "net_profit_growth",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "roe",
    "roa",
    "roic",
    "fcf_ttm",
    "fcf_yield",
    "debt_to_assets",
    "net_debt_to_ebitda",
    "pe_ttm",
    "ev_ebitda",
    "market_cap",
    "volatility",
    "max_drawdown",
)
BANK_PEER_METRICS = (
    "roe",
    "roa",
    "net_profit_growth",
    "revenue_growth",
    "net_interest_margin",
    "cost_income_ratio",
    "non_performing_loan_ratio",
    "provision_coverage_ratio",
    "capital_adequacy_ratio",
    "pe_ttm",
    "pb",
    "market_cap",
    "volatility",
    "max_drawdown",
)
METRIC_ALIASES = {
    "revenue_growth": "revenue_yoy",
    "net_profit_growth": "net_profit_yoy",
    "debt_to_assets": "liability_ratio",
    "ev_ebitda": "ev_to_ebitda",
    "volatility": "annualized_volatility",
    "max_drawdown": "maximum_drawdown",
    "fcf": "fcf_ttm",
    "pe": "pe_ttm",
}
BANK_INDUSTRY_MARKERS = ("银行", "bank")
ADVICE_CAVEAT = "Not investment advice. Scenario output is for research only."
TARGET_PRICE_TERMS = ("target price", "目标价", "buy", "sell", "hold", "买入", "卖出", "持有")


@dataclass(frozen=True)
class PeerCandidate:
    symbol: str
    name: str | None
    exchange: str | None
    industry: str | None
    sector: str | None
    market_cap: float | None
    revenue: float | None
    selected: bool
    reason: str
    similarity_score: float
    source: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class PeerSetResult:
    symbol: str
    as_of_date: str
    peer_set_id: int | None
    peer_set_hash: str
    candidates: tuple[PeerCandidate, ...]
    selected_symbols: tuple[str, ...]
    quality_flags: tuple[str, ...]
    limitations: tuple[str, ...]
    version: str = PEER_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "as_of_date": self.as_of_date,
            "peer_set_id": self.peer_set_id,
            "peer_set_hash": self.peer_set_hash,
            "candidates": [asdict(candidate) for candidate in self.candidates],
            "selected_symbols": list(self.selected_symbols),
            "quality_flags": list(self.quality_flags),
            "limitations": list(self.limitations),
            "version": self.version,
        }


@dataclass(frozen=True)
class ValuationAssumptionSet:
    assumption_set_id: str
    symbol: str
    model_type: str
    scenario: str
    revenue_growth: float = 0.03
    margin: float | None = None
    fcf_margin: float = 0.08
    discount_rate: float = 0.10
    terminal_growth: float = 0.02
    projection_years: int = 5
    tax_rate: float | None = None
    capex_intensity: float | None = None
    working_capital_intensity: float | None = None
    peer_multiple: float | None = None
    created_by: str = "system"
    source: str = "default"
    version: str = "stage5-assumptions-v1"


class PeerSetService:
    def build(
        self,
        symbol: str,
        *,
        as_of_date: str | None = None,
        manual_peers: list[str] | None = None,
        exclude_symbols: list[str] | None = None,
        min_peer_count: int = 3,
        max_peer_count: int = 10,
        persist: bool = True,
    ) -> PeerSetResult:
        effective_as_of = as_of_date or date.today().isoformat()
        target = CompanyRepository().get(symbol)
        if target is None:
            raise ValueError("company_not_found")
        industry = _clean(target.get("industry"))
        if industry is None:
            return _empty_peer_set(symbol, effective_as_of, "insufficient_peer_data")

        excluded = {symbol.upper(), *(item.upper() for item in (exclude_symbols or []))}
        manual = [item.upper() for item in manual_peers or [] if item.upper() not in excluded]
        target_is_bank = _is_bank(industry)
        candidates: list[PeerCandidate] = []
        with session_scope() as session:
            companies = [
                {
                    "symbol": company.symbol,
                    "company_name": company.company_name,
                    "exchange": company.exchange,
                    "industry": company.industry,
                }
                for company in session.scalars(select(Company).order_by(Company.symbol)).all()
            ]
        for company in companies:
            if str(company["symbol"]).upper() in excluded:
                continue
            candidate_industry = _clean(company.get("industry"))
            if candidate_industry is None:
                continue
            if _is_bank(candidate_industry) != target_is_bank:
                continue
            if str(company["symbol"]).upper() in manual:
                candidates.append(
                    self._candidate(company, target, effective_as_of, "manual", 1.0, "manual_peer_override")
                )
                continue
            score, reason = _similarity_score(target, company)
            if score <= 0:
                continue
            candidates.append(self._candidate(company, target, effective_as_of, "auto", score, reason))

        candidates = sorted(candidates, key=lambda item: (-item.similarity_score, item.symbol))
        selected: list[PeerCandidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate.symbol in seen:
                continue
            seen.add(candidate.symbol)
            if len(selected) < max_peer_count:
                selected.append(candidate)
        flags = []
        limitations = ["peer data uses local company metadata and structured facts only"]
        if len(selected) < min_peer_count:
            flags.append("insufficient_peer_count")
        if not selected:
            flags.append("insufficient_peer_data")
        peer_hash = _stable_hash(
            {
                "symbol": symbol,
                "as_of_date": effective_as_of,
                "peers": [asdict(item) for item in selected],
                "excluded": sorted(excluded),
                "version": PEER_VERSION,
            }
        )
        peer_set_id = self._persist(symbol, effective_as_of, peer_hash, selected, flags, limitations) if persist else None
        return PeerSetResult(
            symbol=symbol,
            as_of_date=effective_as_of,
            peer_set_id=peer_set_id,
            peer_set_hash=peer_hash,
            candidates=tuple(selected),
            selected_symbols=tuple(item.symbol for item in selected),
            quality_flags=tuple(flags),
            limitations=tuple(limitations),
        )

    def _candidate(
        self,
        company: dict[str, object],
        target: dict[str, object],
        as_of_date: str,
        source: str,
        score: float,
        reason: str,
    ) -> PeerCandidate:
        candidate_symbol = str(company["symbol"])
        metrics = _metric_map(candidate_symbol, as_of_date=as_of_date, strict_as_of=False)
        return PeerCandidate(
            symbol=candidate_symbol,
            name=_clean(company.get("company_name")),
            exchange=_clean(company.get("exchange")),
            industry=_clean(company.get("industry")),
            sector=_sector(_clean(company.get("industry"))),
            market_cap=_value(metrics, "market_cap"),
            revenue=_value(metrics, "revenue_ttm", "revenue"),
            selected=True,
            reason=reason,
            similarity_score=round(score, 4),
            source=source,
            limitations=tuple(_missing_lineage(metrics, ("market_cap", "revenue_ttm"))),
        )

    def _persist(
        self,
        symbol: str,
        as_of_date: str,
        peer_hash: str,
        selected: list[PeerCandidate],
        flags: list[str],
        limitations: list[str],
    ) -> int:
        with session_scope() as session:
            existing = session.scalar(
                select(PeerSet).where(
                    PeerSet.symbol == symbol,
                    PeerSet.as_of_date == as_of_date,
                    PeerSet.peer_set_hash == peer_hash,
                )
            )
            if existing is not None:
                return int(existing.id)
            peer_set = PeerSet(
                symbol=symbol,
                as_of_date=as_of_date,
                peer_set_hash=peer_hash,
                selection_method="manual" if any(item.source == "manual" for item in selected) else "auto",
                quality_flags=flags,
                limitations=limitations,
                version=PEER_VERSION,
            )
            session.add(peer_set)
            session.flush()
            for item in selected:
                session.add(
                    PeerSetMember(
                        peer_set_id=peer_set.id,
                        symbol=item.symbol,
                        name=item.name,
                        exchange=item.exchange,
                        industry=item.industry,
                        sector=item.sector,
                        market_cap=item.market_cap,
                        revenue=item.revenue,
                        selected=item.selected,
                        reason=item.reason,
                        similarity_score=item.similarity_score,
                        source=item.source,
                        limitations=list(item.limitations),
                    )
                )
            session.flush()
            return int(peer_set.id)


class PeerMetricsMatrixService:
    def build(
        self,
        symbol: str,
        *,
        peer_symbols: list[str] | None = None,
        metric_codes: list[str] | None = None,
        as_of_date: str | None = None,
        strict_as_of: bool = False,
        industry_pack: str = "auto",
    ) -> dict[str, object]:
        effective_as_of = as_of_date or date.today().isoformat()
        target = CompanyRepository().get(symbol)
        if target is None:
            raise ValueError("company_not_found")
        if peer_symbols is None:
            peer_symbols = list(PeerSetService().build(symbol, as_of_date=effective_as_of, persist=True).selected_symbols)
        requested = tuple(metric_codes or _default_metrics(_clean(target.get("industry"))))
        symbols = [symbol, *[peer for peer in peer_symbols if peer != symbol]]
        rows: list[dict[str, object]] = []
        for row_symbol in symbols:
            company = CompanyRepository().get(row_symbol)
            if company is None:
                rows.append({"symbol": row_symbol, "company": None, "metrics": {}, "row_status": "missing_company"})
                continue
            metrics = _metric_map(row_symbol, as_of_date=effective_as_of, strict_as_of=strict_as_of)
            values = {}
            for code in requested:
                canonical = METRIC_ALIASES.get(code, code)
                metric = metrics.get(canonical)
                values[code] = _matrix_cell(code, metric, _clean(company.get("industry")))
            rows.append(
                {
                    "symbol": row_symbol,
                    "name": company.get("company_name"),
                    "exchange": company.get("exchange"),
                    "industry": company.get("industry"),
                    "metrics": values,
                    "row_status": "ok",
                }
            )
        _rank_percentile(rows, requested)
        return {
            "symbol": symbol,
            "as_of_date": effective_as_of,
            "strict_as_of": strict_as_of,
            "industry_pack": industry_pack,
            "columns": list(requested),
            "rows": rows,
            "outlier_policy": "modified_z_score_abs_gt_3_5_or_iqr_fence_1_5",
            "limitations": ["missing and not_applicable values are ignored for rank and percentile"],
        }


class RelativeValuationModel:
    def run(
        self,
        symbol: str,
        *,
        as_of_date: str,
        strict_as_of: bool,
        peer_symbols: list[str] | None = None,
    ) -> dict[str, object]:
        peer_set = PeerSetService().build(symbol, as_of_date=as_of_date, manual_peers=peer_symbols)
        peers = list(peer_symbols or peer_set.selected_symbols)
        matrix = PeerMetricsMatrixService().build(
            symbol,
            peer_symbols=peers,
            metric_codes=["pe_ttm", "ev_ebitda", "fcf_yield", "pb", "ps"],
            as_of_date=as_of_date,
            strict_as_of=strict_as_of,
        )
        rows = cast(list[dict[str, object]], matrix.get("rows", []))
        models = []
        for code in ("pe_ttm", "ev_ebitda", "fcf_yield", "pb", "ps"):
            target_row = rows[0]
            target_metrics = cast(dict[str, dict[str, object]], target_row["metrics"])
            target_cell = target_metrics[code]
            usable = []
            excluded = []
            for row in rows[1:]:
                row_metrics = cast(dict[str, dict[str, object]], row["metrics"])
                cell = row_metrics[code]
                if cell["value"] is None:
                    excluded.append({"symbol": row["symbol"], "reason": cell["missing_reason"] or cell["quality_status"]})
                elif cell.get("outlier"):
                    excluded.append({"symbol": row["symbol"], "reason": "outlier_excluded"})
                else:
                    usable_value = _num(cell.get("value"))
                    if usable_value is not None:
                        usable.append(usable_value)
            if target_cell["value"] is None:
                status = target_cell["missing_reason"] or target_cell["quality_status"]
            elif len(usable) < 2:
                status = "insufficient_peers"
            else:
                status = "calculated"
            stats = _stats(usable)
            models.append(
                {
                    "metric_code": code,
                    "status": status,
                    "target_multiple": target_cell["value"],
                    "peer_median": stats["median"],
                    "peer_average": stats["average"],
                    "peer_percentile": target_cell.get("percentile"),
                    "peer_count": len(peers),
                    "usable_peer_count": len(usable),
                    "excluded_peers": excluded,
                    "relative_position": _relative_position(target_cell.get("percentile")),
                    "implied_value_metric": "scenario value range only",
                    "limitations": _relative_limitations(code, target_cell, len(usable)),
                }
            )
        return {
            "model_type": "relative_valuation",
            "symbol": symbol,
            "as_of_date": as_of_date,
            "peer_set": peer_set.to_dict(),
            "models": models,
            "not_investment_advice": True,
            "caveat": ADVICE_CAVEAT,
        }


class DeterministicScenarioDCF:
    def run(
        self,
        symbol: str,
        *,
        as_of_date: str,
        strict_as_of: bool,
        scenario: str,
        assumptions: dict[str, object] | None = None,
    ) -> dict[str, object]:
        metrics = _metric_map(symbol, as_of_date=as_of_date, strict_as_of=strict_as_of)
        latest = _latest_period_values(symbol, as_of_date=as_of_date, strict_as_of=strict_as_of)
        revenue = _value(metrics, "revenue_ttm", "revenue") or _num(latest.get("revenue"))
        fcf = _value(metrics, "fcf_ttm") or _fcf_from_latest(latest)
        if revenue is None or fcf is None:
            return _dcf_missing(symbol, as_of_date, "insufficient_cash_flow_history")
        base_fcf_margin = fcf / revenue if revenue else None
        assumption_set = build_assumptions(
            symbol,
            "dcf_owner_earnings",
            scenario,
            assumptions,
            observed_fcf_margin=base_fcf_margin,
        )
        warning = "negative_fcf_high_risk" if fcf < 0 else None
        projected: list[dict[str, object]] = []
        prior_revenue = revenue
        discount_rate = assumption_set.discount_rate
        terminal_growth = assumption_set.terminal_growth
        for year in range(1, assumption_set.projection_years + 1):
            projected_revenue = prior_revenue * (1 + assumption_set.revenue_growth)
            projected_fcf = projected_revenue * assumption_set.fcf_margin
            present_value = projected_fcf / ((1 + discount_rate) ** year)
            projected.append(
                {
                    "year": year,
                    "revenue": projected_revenue,
                    "owner_earnings": projected_fcf,
                    "present_value": present_value,
                    "formula": "revenue_t * fcf_margin / (1 + discount_rate) ** year",
                }
            )
            prior_revenue = projected_revenue
        terminal_owner_earnings = _num(projected[-1]["owner_earnings"]) or 0.0
        terminal_fcf = terminal_owner_earnings * (1 + terminal_growth)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth)
        terminal_present_value = terminal_value / ((1 + discount_rate) ** assumption_set.projection_years)
        enterprise_value = sum(_num(item["present_value"]) or 0.0 for item in projected) + terminal_present_value
        net_debt = _value(metrics, "net_debt") or _net_debt_from_latest(latest)
        equity_value = enterprise_value - net_debt if net_debt is not None else None
        shares = _num(latest.get("shares_outstanding"))
        per_share_value = equity_value / shares if equity_value is not None and shares and shares > 0 else None
        return {
            "model_type": "dcf_owner_earnings",
            "status": "calculated",
            "symbol": symbol,
            "as_of_date": as_of_date,
            "scenario_name": scenario,
            "input_metrics": {
                "revenue": revenue,
                "fcf_or_owner_earnings": fcf,
                "net_debt": net_debt,
                "shares_outstanding": shares,
            },
            "assumptions": asdict(assumption_set),
            "results": {
                "enterprise_value_range": _range(enterprise_value),
                "equity_value_range": _range(equity_value) if equity_value is not None else None,
                "per_share_value_range": _range(per_share_value) if per_share_value is not None else None,
                "terminal_value": terminal_value,
                "present_value": enterprise_value,
            },
            "projection": projected,
            "terminal_value": {
                "value": terminal_value,
                "present_value": terminal_present_value,
                "formula": "terminal_owner_earnings / (discount_rate - terminal_growth)",
            },
            "evidence": _evidence_from_metrics(metrics, ("revenue_ttm", "fcf_ttm", "net_debt")),
            "limitations": [
                "sensitivity, not prediction",
                "per-share value omitted unless shares_outstanding has a local structured source",
                *([warning] if warning else []),
            ],
            "not_investment_advice": True,
            "caveat": ADVICE_CAVEAT,
        }


class SensitivityAnalysisService:
    def dcf_grid(self, base_result: dict[str, object]) -> dict[str, object]:
        assumptions = base_result.get("assumptions")
        if not isinstance(assumptions, dict) or base_result.get("status") != "calculated":
            return {"table": [], "warnings": ["insufficient_base_case"], "note": "sensitivity, not prediction"}
        symbol = str(base_result["symbol"])
        as_of = str(base_result["as_of_date"])
        rows = []
        for discount_rate in (0.08, 0.10, 0.12):
            for terminal_growth in (0.01, 0.02, 0.03):
                result = DeterministicScenarioDCF().run(
                    symbol,
                    as_of_date=as_of,
                    strict_as_of=False,
                    scenario=str(base_result.get("scenario_name") or "base"),
                    assumptions={**assumptions, "discount_rate": discount_rate, "terminal_growth": terminal_growth},
                )
                result_payload = result.get("results")
                enterprise_range = result_payload.get("enterprise_value_range") if isinstance(result_payload, dict) else None
                rows.append(
                    {
                        "discount_rate": discount_rate,
                        "terminal_growth": terminal_growth,
                        "enterprise_value_range": enterprise_range,
                    }
                )
        return {
            "table": rows,
            "base_case": base_result.get("results"),
            "assumptions": assumptions,
            "warnings": ["sensitivity, not prediction"],
        }

    def relative_grid(self, relative_result: dict[str, object]) -> dict[str, object]:
        rows = []
        models = relative_result.get("models")
        if not isinstance(models, list):
            return {"table": [], "warnings": ["insufficient_relative_case"]}
        for model in models:
            if not isinstance(model, dict):
                continue
            median_value = _num(model.get("peer_median"))
            rows.append(
                {
                    "metric_code": model.get("metric_code"),
                    "low": median_value * 0.85 if median_value is not None else None,
                    "base": median_value,
                    "high": median_value * 1.15 if median_value is not None else None,
                    "outlier_policy": "modified_z_score_abs_gt_3_5_or_iqr_fence_1_5",
                }
            )
        return {"table": rows, "warnings": ["sensitivity, not prediction"]}


class ValuationLabService:
    def run(
        self,
        symbol: str,
        *,
        model_type: str = "relative_valuation",
        scenario: str = "base",
        as_of_date: str | None = None,
        strict_as_of: bool = False,
        assumptions: dict[str, object] | None = None,
        peer_symbols: list[str] | None = None,
        include_evidence: bool = True,
        include_sensitivity: bool = True,
    ) -> dict[str, object]:
        effective_as_of = as_of_date or date.today().isoformat()
        if CompanyRepository().get(symbol) is None:
            raise ValueError("company_not_found")
        if model_type in {"relative", "relative_valuation"}:
            result = RelativeValuationModel().run(symbol, as_of_date=effective_as_of, strict_as_of=strict_as_of, peer_symbols=peer_symbols)
            sensitivity = SensitivityAnalysisService().relative_grid(result) if include_sensitivity else None
            canonical_model = "relative_valuation"
        elif model_type in {"dcf", "dcf_owner_earnings"}:
            result = DeterministicScenarioDCF().run(
                symbol,
                as_of_date=effective_as_of,
                strict_as_of=strict_as_of,
                scenario=scenario,
                assumptions=assumptions,
            )
            sensitivity = SensitivityAnalysisService().dcf_grid(result) if include_sensitivity else None
            canonical_model = "dcf_owner_earnings"
        else:
            raise ValueError("invalid_model_type")
        payload = {
            "symbol": symbol,
            "as_of_date": effective_as_of,
            "model_type": canonical_model,
            "scenario_name": scenario,
            "input_metrics": result.get("input_metrics", {}),
            "assumptions": result.get("assumptions", {}),
            "results": result,
            "sensitivity": sensitivity,
            "evidence": result.get("evidence", {}) if include_evidence else {},
            "limitations": result.get("limitations", []),
            "generated_at": datetime.now(UTC).isoformat(),
            "valuation_version": VALUATION_VERSION,
            "not_investment_advice": True,
        }
        _guard_no_target_price(payload)
        return self._persist(payload)

    def latest(self, symbol: str, *, as_of_date: str | None = None) -> dict[str, object]:
        effective_as_of = as_of_date or date.today().isoformat()
        return {
            "symbol": symbol,
            "as_of_date": effective_as_of,
            "relative_valuation": self.run(symbol, model_type="relative_valuation", as_of_date=effective_as_of),
            "dcf_owner_earnings": self.run(symbol, model_type="dcf_owner_earnings", as_of_date=effective_as_of),
            "not_investment_advice": True,
        }

    def runs(self, symbol: str) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(select(ValuationRun).where(ValuationRun.symbol == symbol).order_by(ValuationRun.created_at.desc())).all()
            return [_run_dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.scalar(select(ValuationRun).where(ValuationRun.run_id == run_id))
            return _run_dict(row) if row else None

    def _persist(self, payload: dict[str, object]) -> dict[str, object]:
        assumptions = cast(dict[str, object], payload.get("assumptions")) if isinstance(payload.get("assumptions"), dict) else {}
        result_inputs = {
            "symbol": payload["symbol"],
            "as_of_date": payload["as_of_date"],
            "model_type": payload["model_type"],
            "scenario": payload["scenario_name"],
            "assumptions": assumptions,
            "input_metrics": payload.get("input_metrics", {}),
            "results": payload.get("results", {}),
            "version": VALUATION_VERSION,
        }
        assumption_hash = _stable_hash(assumptions)
        input_hash = _stable_hash(result_inputs)
        run_id = f"val_{input_hash[:24]}"
        payload["valuation_run_id"] = run_id
        with session_scope() as session:
            existing = session.scalar(select(ValuationRun).where(ValuationRun.run_id == run_id))
            if existing is None:
                session.add(
                    ValuationRun(
                        run_id=run_id,
                        symbol=str(payload["symbol"]),
                        as_of_date=str(payload["as_of_date"]),
                        model_type=str(payload["model_type"]),
                        scenario=str(payload["scenario_name"]),
                        assumption_hash=assumption_hash,
                        input_hash=input_hash,
                        result_json=payload,
                        evidence_json=payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {},
                        limitations_json=payload.get("limitations") if isinstance(payload.get("limitations"), list) else [],
                        valuation_version=VALUATION_VERSION,
                    )
                )
            if assumptions:
                session.add(
                    ValuationAssumption(
                        assumption_set_id=assumption_hash,
                        symbol=str(payload["symbol"]),
                        model_type=str(payload["model_type"]),
                        scenario=str(payload["scenario_name"]),
                        assumptions_json=assumptions,
                        created_by=str(assumptions.get("created_by", "system")),
                        source=str(assumptions.get("source", "default")),
                    )
                )
        return payload


def build_assumptions(
    symbol: str,
    model_type: str,
    scenario: str,
    overrides: dict[str, object] | None,
    *,
    observed_fcf_margin: float | None,
) -> ValuationAssumptionSet:
    defaults = cast(dict[str, object], {
        "bear": {"revenue_growth": 0.00, "fcf_margin": 0.05, "discount_rate": 0.12, "terminal_growth": 0.01},
        "base": {"revenue_growth": 0.03, "fcf_margin": 0.08, "discount_rate": 0.10, "terminal_growth": 0.02},
        "bull": {"revenue_growth": 0.06, "fcf_margin": 0.10, "discount_rate": 0.09, "terminal_growth": 0.025},
    }.get(scenario, {"revenue_growth": 0.03, "fcf_margin": 0.08, "discount_rate": 0.10, "terminal_growth": 0.02}))
    if observed_fcf_margin is not None and observed_fcf_margin > 0:
        defaults["fcf_margin"] = min(max(observed_fcf_margin, 0.02), 0.15)
    merged = {**defaults, **(overrides or {})}
    discount_rate = _bounded("discount_rate", merged.get("discount_rate"), 0.04, 0.25)
    terminal_growth = _bounded("terminal_growth", merged.get("terminal_growth"), -0.02, 0.04)
    if terminal_growth >= discount_rate:
        raise ValueError("terminal_growth_must_be_below_discount_rate")
    projection_years_raw = _num(merged.get("projection_years", 5))
    projection_years = int(projection_years_raw if projection_years_raw is not None else 5)
    if projection_years < 3 or projection_years > 10:
        raise ValueError("projection_years_out_of_bounds")
    core = {
        "symbol": symbol,
        "model_type": model_type,
        "scenario": scenario,
        "revenue_growth": _bounded("revenue_growth", merged.get("revenue_growth"), -0.20, 0.20),
        "fcf_margin": _bounded("fcf_margin", merged.get("fcf_margin"), -0.20, 0.40),
        "discount_rate": discount_rate,
        "terminal_growth": terminal_growth,
        "projection_years": projection_years,
        "source": str(merged.get("source", "default")),
    }
    assumption_id = _stable_hash(core)
    return ValuationAssumptionSet(
        assumption_set_id=assumption_id,
        symbol=symbol,
        model_type=model_type,
        scenario=scenario,
        revenue_growth=_num(core["revenue_growth"]) or 0.0,
        fcf_margin=_num(core["fcf_margin"]) or 0.0,
        discount_rate=float(discount_rate),
        terminal_growth=float(terminal_growth),
        projection_years=projection_years,
        tax_rate=_optional_float(merged.get("tax_rate")),
        capex_intensity=_optional_float(merged.get("capex_intensity")),
        working_capital_intensity=_optional_float(merged.get("working_capital_intensity")),
        peer_multiple=_optional_float(merged.get("peer_multiple")),
        created_by=str(merged.get("created_by", "system")),
        source=str(core["source"]),
    )


def _metric_map(symbol: str, *, as_of_date: str, strict_as_of: bool) -> dict[str, MetricResult]:
    periods = tuple(FinancialFactRepository().periods(symbol, as_of_date=as_of_date, strict_as_of=strict_as_of))
    prices = tuple(PriceRepository().price_series(symbol, end_date=as_of_date, limit=520))
    currency = next((period.currency for period in periods if period.currency), None)
    context = CalculationContext(
        financial_periods=periods,
        price_series=prices,
        as_of_date=as_of_date,
        strict_as_of=strict_as_of,
        currency=currency,
    )
    return {result.code: result for result in MetricCalculationService().calculate(context, symbol=symbol)}


def _latest_period_values(symbol: str, *, as_of_date: str, strict_as_of: bool) -> dict[str, object]:
    periods = FinancialFactRepository().periods(symbol, as_of_date=as_of_date, strict_as_of=strict_as_of)
    return periods[0].values if periods else {}


def _matrix_cell(code: str, metric: MetricResult | None, industry: str | None) -> dict[str, object]:
    if _is_bank(industry) and code in {"gross_margin", "operating_margin", "roic", "ev_ebitda", "net_debt_to_ebitda"}:
        return {"value": None, "quality_status": "not_applicable", "missing_reason": "not_applicable_to_bank", "unit": "ratio"}
    if metric is None:
        return {"value": None, "quality_status": "missing", "missing_reason": "metric_not_available", "unit": "ratio"}
    return {
        "value": metric.value,
        "quality_status": metric.quality_status if metric.value is not None else "missing",
        "missing_reason": metric.missing_reason,
        "unit": metric.unit,
        "period": metric.period_end,
        "source_fact_ids": list(metric.source_fact_ids),
        "source_price_ids": list(metric.source_price_ids),
        "source_urls": list(metric.source_urls),
        "formula": metric.formula,
        "warnings": list(metric.warnings),
    }


def _rank_percentile(rows: list[dict[str, object]], metric_codes: tuple[str, ...]) -> None:
    for code in metric_codes:
        valid = []
        for row in rows:
            metrics = cast(dict[str, dict[str, object]], row["metrics"])
            cell = metrics[code]
            value = _num(cell.get("value"))
            if value is not None:
                valid.append((row["symbol"], value))
        values = [value for _, value in valid]
        outliers = _outlier_symbols(valid)
        ascending = code in {"debt_to_assets", "net_debt_to_ebitda", "volatility", "max_drawdown"}
        ordered = sorted(valid, key=lambda item: (item[1], item[0]), reverse=not ascending)
        ranks = {symbol: idx + 1 for idx, (symbol, _) in enumerate(ordered)}
        for row in rows:
            metrics = cast(dict[str, dict[str, object]], row["metrics"])
            cell = metrics[code]
            value = _num(cell.get("value"))
            if value is None:
                continue
            less_or_equal = sum(1 for other in values if other <= value)
            percentile = less_or_equal / len(values) if values else None
            cell["rank"] = ranks.get(row["symbol"])
            cell["percentile"] = percentile
            cell["z_score"] = _z_score(value, values)
            cell["outlier"] = row["symbol"] in outliers
            cell["outlier_policy"] = "modified_z_score_abs_gt_3_5_or_iqr_fence_1_5"


def _similarity_score(target: dict[str, object], company: dict[str, object]) -> tuple[float, str]:
    target_industry = _clean(target.get("industry"))
    industry = _clean(company.get("industry"))
    score = 0.0
    reasons = []
    if target_industry and industry == target_industry:
        score += 0.60
        reasons.append("same_industry")
    elif target_industry and industry and _sector(target_industry) == _sector(industry):
        score += 0.25
        reasons.append("same_sector")
    if _clean(target.get("exchange")) and _clean(target.get("exchange")) == _clean(company.get("exchange")):
        score += 0.20
        reasons.append("same_exchange")
    if _listing_board(str(target.get("symbol", ""))) == _listing_board(str(company.get("symbol", ""))):
        score += 0.10
        reasons.append("same_listing_board")
    if score == 0:
        return 0.0, "no_industry_or_market_similarity"
    return score, ",".join(reasons)


def _default_metrics(industry: str | None) -> tuple[str, ...]:
    return BANK_PEER_METRICS if _is_bank(industry) else DEFAULT_PEER_METRICS


def _empty_peer_set(symbol: str, as_of_date: str, reason: str) -> PeerSetResult:
    return PeerSetResult(
        symbol=symbol,
        as_of_date=as_of_date,
        peer_set_id=None,
        peer_set_hash=_stable_hash({"symbol": symbol, "as_of_date": as_of_date, "reason": reason}),
        candidates=(),
        selected_symbols=(),
        quality_flags=(reason,),
        limitations=("industry metadata is required for automatic peer selection",),
    )


def _guard_no_target_price(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    banned = [term for term in TARGET_PRICE_TERMS if term in text]
    allowed = {"target price"}
    if any(term not in allowed for term in banned):
        raise ValueError("investment_advice_or_trading_language_detected")
    for term in INVESTMENT_ADVICE_TERMS:
        if term.lower() in text and term.lower() not in {"target price"}:
            raise ValueError("investment_advice_or_trading_language_detected")


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _clean(value: object) -> str | None:
    return str(value).strip() if value not in (None, "") else None


def _is_bank(industry: str | None) -> bool:
    text = (industry or "").lower()
    return any(marker in text for marker in BANK_INDUSTRY_MARKERS)


def _sector(industry: str | None) -> str | None:
    if industry is None:
        return None
    if _is_bank(industry):
        return "financials"
    if any(marker in industry for marker in ("食品", "饮料", "消费", "酒")):
        return "consumer"
    if any(marker in industry for marker in ("制造", "机械", "电子", "汽车")):
        return "manufacturing"
    return industry


def _listing_board(symbol: str) -> str | None:
    clean = symbol.upper().split(".")[0]
    if clean.startswith("688"):
        return "STAR"
    if clean.startswith("3"):
        return "CHINEXT"
    if clean.startswith(("8", "4")):
        return "BSE"
    if clean.startswith("6"):
        return "SSE_MAIN"
    if clean.startswith(("0", "2")):
        return "SZSE_MAIN"
    return None


def _value(metrics: dict[str, MetricResult], *codes: str) -> float | None:
    for code in codes:
        metric = metrics.get(METRIC_ALIASES.get(code, code))
        if metric and metric.value is not None:
            return float(metric.value)
    return None


def _num(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _optional_float(value: object) -> float | None:
    return _num(value)


def _bounded(name: str, value: object, lower: float, upper: float) -> float:
    parsed = _num(value)
    if parsed is None or parsed < lower or parsed > upper:
        raise ValueError(f"{name}_out_of_bounds")
    return parsed


def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "average": None}
    return {"median": median(values), "average": fmean(values)}


def _z_score(value: float, values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    sigma = pstdev(values)
    return None if sigma == 0 else (value - fmean(values)) / sigma


def _outlier_symbols(values: list[tuple[object, float]]) -> set[object]:
    if len(values) < 4:
        return set()
    ordered = sorted(value for _, value in values)
    q1 = ordered[len(ordered) // 4]
    q3 = ordered[(len(ordered) * 3) // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    med = median(ordered)
    deviations = [abs(value - med) for value in ordered]
    mad = median(deviations)
    outliers = set()
    for symbol, value in values:
        modified_z = 0.0 if mad == 0 else 0.6745 * (value - med) / mad
        if value < lower or value > upper or abs(modified_z) > 3.5:
            outliers.add(symbol)
    return outliers


def _relative_position(percentile: object) -> str:
    value = _num(percentile)
    if value is None:
        return "unknown"
    if value >= 0.75:
        return "above_peer_distribution"
    if value <= 0.25:
        return "below_peer_distribution"
    return "near_peer_median"


def _relative_limitations(code: str, target_cell: dict[str, object], usable_count: int) -> list[str]:
    limitations = ["relative position is not investment advice"]
    if usable_count < 2:
        limitations.append("insufficient_peers")
    if code == "pe_ttm" and target_cell.get("value") is None:
        limitations.append("negative_or_missing_earnings_make_pe_not_applicable")
    if code == "ev_ebitda" and target_cell.get("value") is None:
        limitations.append("negative_or_missing_ebitda_make_ev_ebitda_not_applicable")
    fcf_value = _num(target_cell.get("value"))
    if code == "fcf_yield" and fcf_value is not None and fcf_value < 0:
        limitations.append("negative_fcf_yield_high_risk")
    return limitations


def _missing_lineage(metrics: dict[str, MetricResult], codes: tuple[str, ...]) -> list[str]:
    missing = []
    for code in codes:
        metric = metrics.get(code)
        if metric is None or metric.value is None:
            missing.append(f"{code}:missing_data")
    return missing


def _fcf_from_latest(values: dict[str, object]) -> float | None:
    ocf = _num(values.get("operating_cash_flow"))
    capex = _num(values.get("capital_expenditure"))
    if ocf is None or capex is None:
        return None
    return ocf - (abs(capex))


def _net_debt_from_latest(values: dict[str, object]) -> float | None:
    debt = _num(values.get("interest_bearing_debt")) or _num(values.get("total_debt"))
    cash = _num(values.get("cash_and_equivalents")) or _num(values.get("cash"))
    if debt is None or cash is None:
        return None
    return debt - cash


def _range(value: float | None) -> dict[str, float] | None:
    if value is None:
        return None
    return {"low": value * 0.85, "base": value, "high": value * 1.15}


def _evidence_from_metrics(metrics: dict[str, MetricResult], codes: tuple[str, ...]) -> dict[str, object]:
    evidence: dict[str, object] = {}
    for code in codes:
        metric = metrics.get(code)
        if metric:
            evidence[code] = {
                "source_fact_ids": list(metric.source_fact_ids),
                "source_price_ids": list(metric.source_price_ids),
                "source_urls": list(metric.source_urls),
                "formula": metric.formula,
                "period": metric.period_end,
                "missing_reason": metric.missing_reason,
            }
    return evidence


def _dcf_missing(symbol: str, as_of_date: str, reason: str) -> dict[str, object]:
    return {
        "model_type": "dcf_owner_earnings",
        "status": reason,
        "symbol": symbol,
        "as_of_date": as_of_date,
        "input_metrics": {},
        "assumptions": {},
        "results": {},
        "evidence": {},
        "limitations": [reason, "sensitivity, not prediction"],
        "not_investment_advice": True,
        "caveat": ADVICE_CAVEAT,
    }


def _run_dict(row: ValuationRun) -> dict[str, object]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "symbol": row.symbol,
        "as_of_date": row.as_of_date,
        "model_type": row.model_type,
        "scenario": row.scenario,
        "assumption_hash": row.assumption_hash,
        "input_hash": row.input_hash,
        "result": row.result_json,
        "evidence": row.evidence_json,
        "limitations": row.limitations_json,
        "valuation_version": row.valuation_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
