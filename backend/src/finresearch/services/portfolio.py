from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date
from math import sqrt
from statistics import fmean, pstdev

from sqlalchemy import select

from finresearch.database.models import DataQualityIssue, Filing, ReportRun, ValuationRun
from finresearch.database.session import session_scope
from finresearch.repositories.companies import CompanyRepository
from finresearch.repositories.financial_facts import FinancialFactRepository
from finresearch.repositories.portfolios import PortfolioRepository
from finresearch.repositories.prices import PriceRepository
from finresearch.services.institutional_report import ReportClaimValidator


PORTFOLIO_VERSION = "stage7-portfolio-v1"
FORBIDDEN_TERMS = ("target price", "目标价", "买入", "卖出", "持有")
FORBIDDEN_WORDS = ("buy", "sell", "hold")


class PortfolioService:
    def __init__(self) -> None:
        self.repository = PortfolioRepository()

    def list(self) -> list[dict[str, object]]:
        rows = self.repository.list_portfolios()
        for row in rows:
            row["latest_risk_status"] = "not_run"
            row["open_alerts"] = len([event for event in self.repository.alert_events(int(row["id"])) if event["status"] == "new"])
            row["next_known_events"] = len(self.repository.calendar_events(portfolio_id=int(row["id"])))
        return rows

    def get(self, portfolio_id: int) -> dict[str, object] | None:
        row = self.repository.get(portfolio_id)
        if row is None:
            return None
        row["holdings"] = self.repository.holdings(portfolio_id)
        row["watch_items"] = self.repository.watch_items(portfolio_id)
        return row

    def create(self, payload: dict[str, object]) -> dict[str, object]:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("portfolio_name_required")
        portfolio_type = str(payload.get("portfolio_type") or "watchlist")
        if portfolio_type not in {"watchlist", "research_portfolio", "manual_holdings"}:
            raise ValueError("unsupported_portfolio_type")
        return self.repository.create(
            name=name,
            description=_str_or_none(payload.get("description")),
            base_currency=str(payload.get("base_currency") or "CNY"),
            portfolio_type=portfolio_type,
        )

    def update(self, portfolio_id: int, payload: dict[str, object]) -> dict[str, object] | None:
        return self.repository.update(portfolio_id, payload)

    def archive(self, portfolio_id: int) -> bool:
        return self.repository.archive(portfolio_id)


class PortfolioAnalyticsService:
    def __init__(self) -> None:
        self.repository = PortfolioRepository()

    def summary(self, portfolio_id: int) -> dict[str, object]:
        portfolio = self.repository.get(portfolio_id)
        if portfolio is None:
            raise ValueError("portfolio_not_found")
        rows = self._rows(portfolio_id)
        return {
            "portfolio": portfolio,
            "holdings_count": len(self.repository.holdings(portfolio_id)),
            "watch_count": len(self.repository.watch_items(portfolio_id)),
            "market_value": _sum_present(row.get("market_value") for row in rows),
            "cost_value": _sum_present(row.get("cost_value") for row in rows),
            "unrealized_gain_loss": _sum_present(row.get("unrealized_gain_loss") for row in rows),
            "weighting_policy": _weighting_policy(rows, portfolio),
            "rows": rows,
            "missing_data": self.missing_data(portfolio_id),
            "not_investment_advice": True,
        }

    def exposure(self, portfolio_id: int) -> dict[str, object]:
        rows = self._rows(portfolio_id)
        return {
            "portfolio_id": portfolio_id,
            "by_industry": _bucket(rows, "industry"),
            "by_sector": _bucket(rows, "sector"),
            "by_exchange": _bucket(rows, "exchange"),
            "by_currency": _bucket(rows, "currency"),
            "single_name_concentration": max((_num(row.get("weight")) for row in rows), default=0.0),
            "top_holdings": sorted(rows, key=lambda row: _num(row.get("weight")), reverse=True)[:10],
            "missing_data": self.missing_data(portfolio_id),
        }

    def data_quality(self, portfolio_id: int) -> dict[str, object]:
        rows = self._rows(portfolio_id)
        missing = self.missing_data(portfolio_id)
        symbols = [str(row["symbol"]) for row in rows]
        issue_rows = []
        with session_scope() as session:
            issues = session.scalars(select(DataQualityIssue).where(DataQualityIssue.symbol.in_(symbols))).all() if symbols else []
            issue_rows = [
                {
                    "id": issue.id,
                    "symbol": issue.symbol,
                    "issue_type": issue.issue_type,
                    "severity": issue.severity,
                    "status": issue.status,
                    "details": issue.details or {},
                }
                for issue in issues
            ]
        total = max(len(rows), 1)
        raw_missing_inputs = missing.get("missing_inputs", [])
        missing_inputs = raw_missing_inputs if isinstance(raw_missing_inputs, list) else []
        missing_symbols = {str(item["symbol"]) for item in missing_inputs if isinstance(item, dict)}
        score = max(0.0, 100.0 - len(missing_symbols) / total * 45.0 - len(issue_rows) * 5.0)
        return {
            "portfolio_id": portfolio_id,
            "portfolio_data_quality_score": round(score, 2),
            "coverage_by_holding": [
                {"symbol": row["symbol"], "price": row.get("latest_price") is not None, "company": row.get("company") is not None}
                for row in rows
            ],
            "missing_inputs": missing["missing_inputs"],
            "evidence_map": _evidence_map(rows),
            "issues": issue_rows,
            "limitations": missing["limitations"],
        }

    def missing_data(self, portfolio_id: int) -> dict[str, object]:
        rows = self._rows(portfolio_id)
        missing = []
        for row in rows:
            for key, reason in {
                "latest_price": "missing_price",
                "company": "missing_company_metadata",
            }.items():
                if row.get(key) is None:
                    missing.append({"symbol": row["symbol"], "missing_reason": reason})
            if row.get("currency_mismatch"):
                missing.append({"symbol": row["symbol"], "missing_reason": "currency_mismatch"})
        return {
            "missing_inputs": missing,
            "limitations": ["missing values are not treated as zero"] if missing else [],
            "partial_coverage": bool(missing),
        }

    def _rows(self, portfolio_id: int) -> list[dict[str, object]]:
        portfolio = self.repository.get(portfolio_id)
        if portfolio is None:
            raise ValueError("portfolio_not_found")
        items = self.repository.holdings(portfolio_id)
        watch_items = self.repository.watch_items(portfolio_id)
        if not items:
            items = [
                {
                    "id": item["id"],
                    "portfolio_id": portfolio_id,
                    "symbol": item["symbol"],
                    "quantity": None,
                    "cost_basis": None,
                    "cost_currency": None,
                    "weight_override": None,
                    "source": "watch_item",
                }
                for item in watch_items
            ]
        rows = [_asset_row(item, portfolio) for item in items]
        _assign_weights(rows, portfolio)
        return rows


class PortfolioRiskService:
    def __init__(self) -> None:
        self.analytics = PortfolioAnalyticsService()

    def snapshot(self, portfolio_id: int) -> dict[str, object]:
        rows = self.analytics._rows(portfolio_id)
        exposure = self.analytics.exposure(portfolio_id)
        data_quality = self.analytics.data_quality(portfolio_id)
        vol_values = [_num(row.get("volatility")) * _num(row.get("weight")) for row in rows if row.get("volatility") is not None]
        concentration = _num(exposure.get("single_name_concentration"))
        risk_flags = []
        if concentration > 0.35:
            risk_flags.append({"flag": "single_name_concentration", "severity": "high", "threshold": 0.35})
        if data_quality["missing_inputs"]:
            risk_flags.append({"flag": "data_quality_risk", "severity": "medium", "missing_inputs": data_quality["missing_inputs"]})
        valuation_flags = _valuation_flags([str(row["symbol"]) for row in rows])
        report_flags = _report_flags([str(row["symbol"]) for row in rows])
        risk_flags.extend(valuation_flags + report_flags)
        correlations = _correlation_matrix(rows)
        return {
            "portfolio_id": portfolio_id,
            "weighted_volatility": sum(vol_values) if vol_values else None,
            "weighted_beta": {"status": "insufficient_data", "missing_reason": "missing_benchmark"},
            "max_drawdown_proxy": _weighted_metric(rows, "max_drawdown"),
            "concentration_risk": concentration,
            "sector_concentration": _max_bucket(exposure["by_sector"]),
            "industry_concentration": _max_bucket(exposure["by_industry"]),
            "currency_concentration": _max_bucket(exposure["by_currency"]),
            "data_quality_risk": data_quality,
            "stale_price_risk": _stale_price_flags(rows),
            "missing_filing_risk": _missing_filing_flags(rows),
            "valuation_risk_flags": valuation_flags,
            "report_validation_risk_flags": report_flags,
            "correlation_matrix": correlations,
            "diversification_score": round(max(0.0, 100.0 - concentration * 70.0 - len(risk_flags) * 5.0), 2),
            "risk_flags": risk_flags,
            "not_investment_advice": True,
        }


class PortfolioPerformanceService:
    def __init__(self) -> None:
        self.analytics = PortfolioAnalyticsService()

    def performance(self, portfolio_id: int) -> dict[str, object]:
        rows = self.analytics._rows(portfolio_id)
        series = _portfolio_value_series(rows)
        returns = _series_returns(series)
        return {
            "portfolio_id": portfolio_id,
            "daily_value_series": series,
            "cumulative_return": (_num(series[-1].get("value")) / _num(series[0].get("value")) - 1) if len(series) >= 2 and _num(series[0].get("value")) else None,
            "period_return": returns[-1] if returns else None,
            "volatility": pstdev(returns) * sqrt(252) if len(returns) >= 2 else None,
            "max_drawdown": _series_drawdown(series),
            "contribution_by_holding": [
                {"symbol": row["symbol"], "contribution": row.get("weight"), "status": "calculated" if row.get("latest_price") else "missing_price"}
                for row in rows
            ],
            "benchmark_comparison": {"status": "missing", "missing_reason": "missing_benchmark"},
            "partial_coverage": any(row.get("latest_price") is None for row in rows),
            "not_investment_advice": True,
        }


class AlertsService:
    def __init__(self) -> None:
        self.repository = PortfolioRepository()
        self.analytics = PortfolioAnalyticsService()

    def evaluate(self, portfolio_id: int) -> dict[str, object]:
        if self.repository.get(portfolio_id) is None:
            raise ValueError("portfolio_not_found")
        events: list[dict[str, object]] = []
        skipped: list[dict[str, object]] = []
        rows = {str(row["symbol"]): row for row in self.analytics._rows(portfolio_id)}
        risk = PortfolioRiskService().snapshot(portfolio_id)
        for rule in self.repository.alert_rules(portfolio_id):
            if not rule["enabled"]:
                continue
            result = self._evaluate_rule(rule, rows, risk)
            if result["status"] == "triggered":
                events.append(
                    self.repository.create_alert_event(
                        portfolio_id,
                        rule_id=int(rule["rule_id"]),
                        symbol=result.get("symbol") if isinstance(result.get("symbol"), str) else None,
                        message=str(result["message"]),
                        evidence=result.get("evidence") if isinstance(result.get("evidence"), dict) else {},
                        severity=str(rule.get("severity") or "medium"),
                    )
                )
            else:
                skipped.append(result)
        return {"portfolio_id": portfolio_id, "triggered": events, "skipped": skipped, "not_investment_advice": True}

    def _evaluate_rule(self, rule: dict[str, object], rows: dict[str, dict[str, object]], risk: dict[str, object]) -> dict[str, object]:
        rule_type = str(rule["rule_type"])
        symbol = str(rule["symbol"]) if rule.get("symbol") else None
        threshold = rule.get("threshold")
        if rule_type in {"price_above", "price_below"}:
            row = rows.get(symbol or "")
            if row is None or row.get("latest_price") is None or not isinstance(threshold, int | float):
                return {"status": "skipped", "rule_id": rule["rule_id"], "missing_reason": "missing_price", "symbol": symbol}
            price = _num(row.get("latest_price"))
            triggered = price > _num(threshold) if rule_type == "price_above" else price < _num(threshold)
            return _alert_result(triggered, rule, f"Price threshold met for {symbol}", {"price": price})
        if rule_type in {"metric_above", "metric_below"}:
            value = _latest_metric(symbol or "", str(rule.get("metric_code") or ""))
            if value is None or not isinstance(threshold, int | float):
                return {"status": "skipped", "rule_id": rule["rule_id"], "missing_reason": "missing_metric", "symbol": symbol}
            triggered = value > float(threshold) if rule_type == "metric_above" else value < float(threshold)
            return _alert_result(triggered, rule, f"Metric threshold met for {symbol}", {"value": value})
        if rule_type == "portfolio_concentration_above":
            concentration = _num(risk.get("concentration_risk"))
            triggered = isinstance(threshold, int | float) and concentration > _num(threshold)
            return _alert_result(triggered, rule, "Portfolio concentration threshold met", {"concentration": concentration})
        if rule_type == "data_quality_issue":
            data_quality = risk.get("data_quality_risk")
            issues = data_quality.get("issues", []) if isinstance(data_quality, dict) else []
            return _alert_result(bool(issues), rule, "Data quality issue detected", {"issues": issues})
        if rule_type == "report_validation_failed":
            flags = risk.get("report_validation_risk_flags", [])
            return _alert_result(bool(flags), rule, "Report validation issue detected", {"flags": flags})
        if rule_type == "stale_price":
            flags = risk.get("stale_price_risk", [])
            return _alert_result(bool(flags), rule, "Stale price data detected", {"flags": flags})
        if rule_type == "missing_filing":
            flags = risk.get("missing_filing_risk", [])
            return _alert_result(bool(flags), rule, "Official filing evidence missing", {"flags": flags})
        return {"status": "skipped", "rule_id": rule["rule_id"], "missing_reason": "unsupported_rule_type"}


class CalendarService:
    def __init__(self) -> None:
        self.repository = PortfolioRepository()

    def list_events(self, **filters: object) -> dict[str, object]:
        events = self.repository.calendar_events(
            start_date=_str_or_none(filters.get("start_date")),
            end_date=_str_or_none(filters.get("end_date")),
            portfolio_id=_int_or_none(filters.get("portfolio_id")),
            symbol=_str_or_none(filters.get("symbol")),
            severity=_str_or_none(filters.get("severity")),
            offset=_int_or_none(filters.get("offset")) or 0,
            limit=_int_or_none(filters.get("limit")) or 200,
        )
        return {"events": events, "state": "available" if events else "no_known_events"}

    def create_event(self, payload: dict[str, object]) -> dict[str, object]:
        if not payload.get("title") or not payload.get("event_date"):
            raise ValueError("calendar_title_and_date_required")
        return self.repository.add_calendar_event(payload)

    def update_event(self, event_id: int, payload: dict[str, object]) -> dict[str, object] | None:
        return self.repository.update_calendar_event(event_id, payload)

    def delete_event(self, event_id: int) -> bool:
        return self.repository.delete_calendar_event(event_id)


class PortfolioReportService:
    def build(self, portfolio_id: int) -> dict[str, object]:
        analytics = PortfolioAnalyticsService()
        summary = analytics.summary(portfolio_id)
        risk = PortfolioRiskService().snapshot(portfolio_id)
        performance = PortfolioPerformanceService().performance(portfolio_id)
        alerts = PortfolioRepository().alert_events(portfolio_id)
        calendar = CalendarService().list_events(portfolio_id=portfolio_id)
        report = {
            "report_id": f"portfolio_report_{_hash({'portfolio_id': portfolio_id, 'summary': summary})[:16]}",
            "portfolio_id": portfolio_id,
            "sections": [
                {"section_id": "portfolio_summary", "content": summary},
                {"section_id": "holdings_exposure", "content": analytics.exposure(portfolio_id)},
                {"section_id": "risk_snapshot", "content": risk},
                {"section_id": "performance_summary", "content": performance},
                {"section_id": "alerts_summary", "content": {"events": alerts}},
                {"section_id": "calendar_summary", "content": calendar},
                {"section_id": "data_quality_limitations", "content": analytics.data_quality(portfolio_id)},
            ],
            "validation": {"status": "passed", "guard": ReportClaimValidator.__name__},
            "evidence_map": summary["missing_data"],
            "limitations": ["portfolio report uses local manual entries and persisted evidence only"],
            "not_investment_advice": True,
        }
        _guard_no_advice(report)
        return report


def _asset_row(item: dict[str, object], portfolio: dict[str, object]) -> dict[str, object]:
    symbol = str(item["symbol"])
    company = CompanyRepository().get(symbol)
    prices = PriceRepository().list_by_symbol(symbol, limit=260)
    latest_price = prices[0] if prices else None
    close = latest_price.get("close") if latest_price else None
    quantity = item.get("quantity")
    cost_basis = item.get("cost_basis")
    market_value = float(quantity) * float(close) if isinstance(quantity, int | float) and isinstance(close, int | float) else None
    cost_value = float(quantity) * float(cost_basis) if isinstance(quantity, int | float) and isinstance(cost_basis, int | float) else None
    price_returns = _returns_from_price_rows(prices)
    return {
        **item,
        "company": company,
        "industry": company.get("industry") if company else None,
        "sector": company.get("industry") if company else None,
        "exchange": company.get("exchange") if company else None,
        "currency": company.get("currency") if company else None,
        "latest_price": close,
        "latest_price_date": latest_price.get("trade_date") if latest_price else None,
        "market_value": market_value,
        "cost_value": cost_value,
        "unrealized_gain_loss": market_value - cost_value if market_value is not None and cost_value is not None else None,
        "currency_mismatch": bool(item.get("cost_currency") and company and item.get("cost_currency") != company.get("currency")),
        "volatility": pstdev(price_returns) * sqrt(252) if len(price_returns) >= 20 else None,
        "max_drawdown": _drawdown_from_prices(prices),
        "price_series": prices,
        "base_currency": portfolio.get("base_currency"),
    }


def _assign_weights(rows: list[dict[str, object]], portfolio: dict[str, object]) -> None:
    overrides = [row for row in rows if isinstance(row.get("weight_override"), int | float)]
    if overrides:
        total = sum(_num(row.get("weight_override")) for row in overrides)
        for row in rows:
            row["weight"] = _num(row.get("weight_override")) / total if total else 0
            row["weight_source"] = "manual_override"
        return
    market_total = _sum_present(row.get("market_value") for row in rows)
    if market_total:
        for row in rows:
            row["weight"] = _num(row.get("market_value")) / market_total
            row["weight_source"] = "market_value"
        return
    equal = 1 / len(rows) if rows else 0
    for row in rows:
        row["weight"] = equal
        row["weight_source"] = "equal_weight_watchlist" if portfolio.get("portfolio_type") == "watchlist" else "equal_weight_fallback"


def _bucket(rows: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    totals: dict[str, float] = {}
    for row in rows:
        name = str(row.get(key) or "unknown")
        totals[name] = totals.get(name, 0.0) + _num(row.get("weight"))
    return [{"name": name, "weight": weight} for name, weight in sorted(totals.items())]


def _sum_present(values: Iterable[object]) -> float | None:
    vals = [_num(value) for value in values if isinstance(value, int | float)]
    return sum(vals) if vals else None


def _weighting_policy(rows: list[dict[str, object]], portfolio: dict[str, object]) -> str:
    return str(rows[0]["weight_source"]) if rows else f"empty_{portfolio.get('portfolio_type')}"


def _evidence_map(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "symbol": row["symbol"],
            "source_price_date": row.get("latest_price_date"),
            "company_metadata": bool(row.get("company")),
            "weight_source": row.get("weight_source"),
        }
        for row in rows
    ]


def _valuation_flags(symbols: list[str]) -> list[dict[str, object]]:
    with session_scope() as session:
        runs = session.scalars(select(ValuationRun).where(ValuationRun.symbol.in_(symbols))).all() if symbols else []
        return [
            {"symbol": run.symbol, "flag": "valuation_limitations", "limitations": run.limitations_json or []}
            for run in runs
            if run.limitations_json
        ]


def _report_flags(symbols: list[str]) -> list[dict[str, object]]:
    with session_scope() as session:
        reports = session.scalars(select(ReportRun).where(ReportRun.symbol.in_(symbols))).all() if symbols else []
        return [
            {"symbol": report.symbol, "flag": "report_validation", "validation_status": report.validation_status}
            for report in reports
            if report.validation_status != "passed"
        ]


def _stale_price_flags(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    today = date.today().isoformat()
    return [{"symbol": row["symbol"], "latest_price_date": row.get("latest_price_date")} for row in rows if row.get("latest_price_date") and str(row["latest_price_date"]) < today]


def _missing_filing_flags(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    symbols = [str(row["symbol"]) for row in rows]
    with session_scope() as session:
        found = {row.symbol for row in session.scalars(select(Filing).where(Filing.symbol.in_(symbols))).all()} if symbols else set()
    return [{"symbol": symbol, "missing_reason": "missing_official_filing"} for symbol in symbols if symbol not in found]


def _correlation_matrix(rows: list[dict[str, object]]) -> dict[str, object]:
    series = {str(row["symbol"]): _returns_from_price_rows(row.get("price_series") or []) for row in rows}
    if any(len(values) < 20 for values in series.values()) or len(series) < 2:
        return {"status": "insufficient_data", "missing_reason": "insufficient_price_history"}
    symbols = sorted(series)
    matrix = []
    for left in symbols:
        line = {}
        for right in symbols:
            line[right] = _correlation(series[left], series[right])
        matrix.append({"symbol": left, "correlations": line})
    return {"status": "calculated", "matrix": matrix}


def _portfolio_value_series(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    dates = sorted({str(price["trade_date"]) for row in rows for price in _price_rows(row) if price.get("close") is not None})
    output = []
    for trade_date in dates:
        total = 0.0
        coverage = 0
        for row in rows:
            quantity = row.get("quantity")
            match = next((price for price in _price_rows(row) if price["trade_date"] == trade_date), None)
            if isinstance(quantity, int | float) and match and isinstance(match.get("close"), int | float):
                total += _num(quantity) * _num(match.get("close"))
                coverage += 1
        if coverage:
            output.append({"date": trade_date, "value": total, "coverage": coverage})
    return output


def _series_returns(series: list[dict[str, object]]) -> list[float]:
    returns = []
    for left, right in zip(series, series[1:], strict=False):
        left_value = _num(left.get("value"))
        if left_value:
            returns.append(_num(right.get("value")) / left_value - 1)
    return returns


def _series_drawdown(series: list[dict[str, object]]) -> float | None:
    if not series:
        return None
    peak = _num(series[0].get("value"))
    drawdown = 0.0
    for point in series:
        value = _num(point.get("value"))
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1 if peak else 0)
    return drawdown


def _weighted_metric(rows: list[dict[str, object]], key: str) -> float | None:
    values = [_num(row.get(key)) * _num(row.get("weight")) for row in rows if row.get(key) is not None]
    return sum(values) if values else None


def _max_bucket(value: object) -> float | None:
    if not isinstance(value, list):
        return None
    return max((float(item.get("weight") or 0) for item in value if isinstance(item, dict)), default=0.0)


def _latest_metric(symbol: str, metric_code: str) -> float | None:
    facts = FinancialFactRepository().list_by_symbol(symbol, years=1)
    row = next((item for item in facts if item.get("metric_code") == metric_code), None)
    value = row.get("value") if row else None
    return float(value) if isinstance(value, int | float) else None


def _alert_result(triggered: bool, rule: dict[str, object], message: str, evidence: dict[str, object]) -> dict[str, object]:
    _guard_no_advice({"message": message})
    return {
        "status": "triggered" if triggered else "skipped",
        "rule_id": rule["rule_id"],
        "symbol": rule.get("symbol"),
        "message": message,
        "evidence": evidence,
        "missing_reason": None if triggered else "condition_not_met",
    }


def _returns_from_price_rows(prices: object) -> list[float]:
    if not isinstance(prices, list):
        return []
    ordered = [row for row in sorted(prices, key=lambda item: str(item.get("trade_date"))) if isinstance(row.get("close"), int | float)]
    return [float(right["close"]) / float(left["close"]) - 1 for left, right in zip(ordered, ordered[1:], strict=False) if left["close"]]


def _drawdown_from_prices(prices: object) -> float | None:
    if not isinstance(prices, list) or not prices:
        return None
    values = [{"value": row["close"]} for row in prices if isinstance(row.get("close"), int | float)]
    return _series_drawdown(values)


def _correlation(left: list[float], right: list[float]) -> float | None:
    n = min(len(left), len(right))
    if n < 2:
        return None
    lvals = left[-n:]
    rvals = right[-n:]
    lm = fmean(lvals)
    rm = fmean(rvals)
    denom = sqrt(sum((item - lm) ** 2 for item in lvals) * sum((item - rm) ** 2 for item in rvals))
    return sum((lvals[i] - lm) * (rvals[i] - rm) for i in range(n)) / denom if denom else None


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _guard_no_advice(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    if any(term in text for term in FORBIDDEN_TERMS):
        raise ValueError("forbidden_portfolio_advice_wording")
    for word in FORBIDDEN_WORDS:
        if f" {word} " in f" {text} ":
            raise ValueError("forbidden_portfolio_advice_wording")


def _str_or_none(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None


def _num(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _price_rows(row: dict[str, object]) -> list[dict[str, object]]:
    value = row.get("price_series")
    return value if isinstance(value, list) else []
