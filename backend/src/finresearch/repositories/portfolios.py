from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from finresearch.database.models import (
    Portfolio,
    PortfolioAlertEvent,
    PortfolioAlertRule,
    PortfolioCalendarEvent,
    PortfolioHolding,
    PortfolioWatchItem,
)
from finresearch.database.session import session_scope


class PortfolioRepository:
    def list_portfolios(self, *, include_archived: bool = False) -> list[dict[str, object]]:
        with session_scope() as session:
            statement = select(Portfolio).order_by(Portfolio.id)
            if not include_archived:
                statement = statement.where(Portfolio.archived.is_(False))
            return [_portfolio_dict(row) for row in session.scalars(statement).all()]

    def get(self, portfolio_id: int) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(Portfolio, portfolio_id)
            return _portfolio_dict(row) if row and not row.archived else None

    def create(
        self,
        *,
        name: str,
        description: str | None = None,
        base_currency: str = "CNY",
        portfolio_type: str = "watchlist",
    ) -> dict[str, object]:
        with session_scope() as session:
            row = Portfolio(
                name=name,
                description=description,
                base_currency=base_currency,
                portfolio_type=portfolio_type,
                archived=False,
            )
            session.add(row)
            session.flush()
            return _portfolio_dict(row)

    def update(self, portfolio_id: int, payload: dict[str, object]) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(Portfolio, portfolio_id)
            if row is None or row.archived:
                return None
            for field in ("name", "description", "base_currency", "portfolio_type"):
                if field in payload:
                    setattr(row, field, payload[field])
            session.flush()
            return _portfolio_dict(row)

    def archive(self, portfolio_id: int) -> bool:
        with session_scope() as session:
            row = session.get(Portfolio, portfolio_id)
            if row is None:
                return False
            row.archived = True
            return True

    def holdings(self, portfolio_id: int, *, offset: int = 0, limit: int = 200) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(PortfolioHolding)
                .where(PortfolioHolding.portfolio_id == portfolio_id)
                .order_by(PortfolioHolding.symbol)
                .offset(max(0, offset))
                .limit(max(1, min(limit, 500)))
            ).all()
            return [_holding_dict(row) for row in rows]

    def add_holding(self, portfolio_id: int, payload: dict[str, object]) -> dict[str, object]:
        symbol = str(payload["symbol"]).upper()
        with session_scope() as session:
            row = session.scalar(
                select(PortfolioHolding).where(
                    PortfolioHolding.portfolio_id == portfolio_id,
                    PortfolioHolding.symbol == symbol,
                )
            )
            if row is None:
                row = PortfolioHolding(portfolio_id=portfolio_id, symbol=symbol, source="manual")
                session.add(row)
            _apply_holding(row, payload)
            session.flush()
            return _holding_dict(row)

    def update_holding(self, portfolio_id: int, holding_id: int, payload: dict[str, object]) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(PortfolioHolding, holding_id)
            if row is None or row.portfolio_id != portfolio_id:
                return None
            _apply_holding(row, payload)
            session.flush()
            return _holding_dict(row)

    def delete_holding(self, portfolio_id: int, holding_id: int) -> bool:
        with session_scope() as session:
            row = session.get(PortfolioHolding, holding_id)
            if row is None or row.portfolio_id != portfolio_id:
                return False
            session.delete(row)
            return True

    def watch_items(self, portfolio_id: int, *, offset: int = 0, limit: int = 200) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(PortfolioWatchItem)
                .where(PortfolioWatchItem.portfolio_id == portfolio_id)
                .order_by(PortfolioWatchItem.symbol)
                .offset(max(0, offset))
                .limit(max(1, min(limit, 500)))
            ).all()
            return [_watch_item_dict(row) for row in rows]

    def add_watch_item(self, portfolio_id: int, payload: dict[str, object]) -> dict[str, object]:
        symbol = str(payload["symbol"]).upper()
        with session_scope() as session:
            row = session.scalar(
                select(PortfolioWatchItem).where(
                    PortfolioWatchItem.portfolio_id == portfolio_id,
                    PortfolioWatchItem.symbol == symbol,
                )
            )
            if row is None:
                row = PortfolioWatchItem(portfolio_id=portfolio_id, symbol=symbol)
                session.add(row)
            _apply_watch_item(row, payload)
            session.flush()
            return _watch_item_dict(row)

    def update_watch_item(self, portfolio_id: int, item_id: int, payload: dict[str, object]) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(PortfolioWatchItem, item_id)
            if row is None or row.portfolio_id != portfolio_id:
                return None
            _apply_watch_item(row, payload)
            session.flush()
            return _watch_item_dict(row)

    def delete_watch_item(self, portfolio_id: int, item_id: int) -> bool:
        with session_scope() as session:
            row = session.get(PortfolioWatchItem, item_id)
            if row is None or row.portfolio_id != portfolio_id:
                return False
            session.delete(row)
            return True

    def alert_rules(self, portfolio_id: int) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(PortfolioAlertRule)
                .where(PortfolioAlertRule.portfolio_id == portfolio_id)
                .order_by(PortfolioAlertRule.id)
            ).all()
            return [_alert_rule_dict(row) for row in rows]

    def add_alert_rule(self, portfolio_id: int, payload: dict[str, object]) -> dict[str, object]:
        with session_scope() as session:
            row = PortfolioAlertRule(
                portfolio_id=portfolio_id,
                symbol=_upper_or_none(payload.get("symbol")),
                rule_type=str(payload["rule_type"]),
                metric_code=_str_or_none(payload.get("metric_code")),
                threshold=_float_or_none(payload.get("threshold")),
                direction=_str_or_none(payload.get("direction")),
                enabled=bool(payload.get("enabled", True)),
                severity=str(payload.get("severity", "medium")),
            )
            session.add(row)
            session.flush()
            return _alert_rule_dict(row)

    def update_alert_rule(self, portfolio_id: int, rule_id: int, payload: dict[str, object]) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(PortfolioAlertRule, rule_id)
            if row is None or row.portfolio_id != portfolio_id:
                return None
            for field in ("rule_type", "metric_code", "threshold", "direction", "enabled", "severity"):
                if field in payload:
                    setattr(row, field, payload[field])
            if "symbol" in payload:
                row.symbol = _upper_or_none(payload.get("symbol"))
            session.flush()
            return _alert_rule_dict(row)

    def delete_alert_rule(self, portfolio_id: int, rule_id: int) -> bool:
        with session_scope() as session:
            row = session.get(PortfolioAlertRule, rule_id)
            if row is None or row.portfolio_id != portfolio_id:
                return False
            session.delete(row)
            return True

    def alert_events(self, portfolio_id: int, *, offset: int = 0, limit: int = 200) -> list[dict[str, object]]:
        with session_scope() as session:
            rows = session.scalars(
                select(PortfolioAlertEvent)
                .where(PortfolioAlertEvent.portfolio_id == portfolio_id)
                .order_by(PortfolioAlertEvent.triggered_at.desc(), PortfolioAlertEvent.id.desc())
                .offset(max(0, offset))
                .limit(max(1, min(limit, 500)))
            ).all()
            return [_alert_event_dict(row) for row in rows]

    def create_alert_event(
        self,
        portfolio_id: int,
        *,
        rule_id: int | None,
        symbol: str | None,
        message: str,
        evidence: dict[str, object],
        severity: str,
    ) -> dict[str, object]:
        now = datetime.now(UTC).isoformat()
        with session_scope() as session:
            row = PortfolioAlertEvent(
                portfolio_id=portfolio_id,
                rule_id=rule_id,
                symbol=symbol,
                triggered_at=now,
                message=message,
                evidence_json=evidence,
                status="new",
                severity=severity,
            )
            session.add(row)
            if rule_id is not None:
                rule = session.get(PortfolioAlertRule, rule_id)
                if rule:
                    rule.last_triggered_at = now
                    rule.last_evaluated_at = now
            session.flush()
            return _alert_event_dict(row)

    def set_alert_event_status(self, portfolio_id: int, event_id: int, status: str) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(PortfolioAlertEvent, event_id)
            if row is None or row.portfolio_id != portfolio_id:
                return None
            row.status = status
            session.flush()
            return _alert_event_dict(row)

    def calendar_events(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        portfolio_id: int | None = None,
        symbol: str | None = None,
        severity: str | None = None,
        offset: int = 0,
        limit: int = 200,
    ) -> list[dict[str, object]]:
        with session_scope() as session:
            statement = select(PortfolioCalendarEvent).order_by(PortfolioCalendarEvent.event_date, PortfolioCalendarEvent.id)
            if start_date:
                statement = statement.where(PortfolioCalendarEvent.event_date >= start_date)
            if end_date:
                statement = statement.where(PortfolioCalendarEvent.event_date <= end_date)
            if portfolio_id is not None:
                statement = statement.where(PortfolioCalendarEvent.portfolio_id == portfolio_id)
            if symbol:
                statement = statement.where(PortfolioCalendarEvent.symbol == symbol.upper())
            if severity:
                statement = statement.where(PortfolioCalendarEvent.severity == severity)
            statement = statement.offset(max(0, offset)).limit(max(1, min(limit, 500)))
            return [_calendar_event_dict(row) for row in session.scalars(statement).all()]

    def add_calendar_event(self, payload: dict[str, object]) -> dict[str, object]:
        with session_scope() as session:
            row = PortfolioCalendarEvent(
                portfolio_id=_int_or_none(payload.get("portfolio_id")),
                symbol=_upper_or_none(payload.get("symbol")),
                event_type=str(payload.get("event_type", "manual")),
                title=str(payload["title"]),
                event_date=str(payload["event_date"]),
                source=str(payload.get("source", "manual")),
                filing_id=_int_or_none(payload.get("filing_id")),
                report_run_id=_int_or_none(payload.get("report_run_id")),
                notes=_str_or_none(payload.get("notes")),
                severity=str(payload.get("severity", "medium")),
            )
            session.add(row)
            session.flush()
            return _calendar_event_dict(row)

    def update_calendar_event(self, event_id: int, payload: dict[str, object]) -> dict[str, object] | None:
        with session_scope() as session:
            row = session.get(PortfolioCalendarEvent, event_id)
            if row is None:
                return None
            for field in ("event_type", "title", "event_date", "source", "notes", "severity"):
                if field in payload:
                    setattr(row, field, payload[field])
            if "portfolio_id" in payload:
                row.portfolio_id = _int_or_none(payload.get("portfolio_id"))
            if "symbol" in payload:
                row.symbol = _upper_or_none(payload.get("symbol"))
            session.flush()
            return _calendar_event_dict(row)

    def delete_calendar_event(self, event_id: int) -> bool:
        with session_scope() as session:
            row = session.get(PortfolioCalendarEvent, event_id)
            if row is None:
                return False
            session.delete(row)
            return True


def _portfolio_dict(row: Portfolio) -> dict[str, object]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "base_currency": row.base_currency,
        "portfolio_type": row.portfolio_type,
        "archived": row.archived,
        "holdings_count": len(row.holdings),
        "watch_count": len(row.watch_items),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _holding_dict(row: PortfolioHolding) -> dict[str, object]:
    return {
        "id": row.id,
        "portfolio_id": row.portfolio_id,
        "symbol": row.symbol,
        "quantity": row.quantity,
        "cost_basis": row.cost_basis,
        "cost_currency": row.cost_currency,
        "position_date": row.position_date,
        "weight_override": row.weight_override,
        "notes": row.notes,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _watch_item_dict(row: PortfolioWatchItem) -> dict[str, object]:
    return {
        "id": row.id,
        "portfolio_id": row.portfolio_id,
        "symbol": row.symbol,
        "thesis": row.thesis,
        "interest_level": row.interest_level,
        "tags": row.tags or [],
        "notes": row.notes,
        "added_at": row.added_at.isoformat() if row.added_at else None,
    }


def _alert_rule_dict(row: PortfolioAlertRule) -> dict[str, object]:
    return {
        "rule_id": row.id,
        "portfolio_id": row.portfolio_id,
        "symbol": row.symbol,
        "rule_type": row.rule_type,
        "metric_code": row.metric_code,
        "threshold": row.threshold,
        "direction": row.direction,
        "enabled": row.enabled,
        "severity": row.severity,
        "last_evaluated_at": row.last_evaluated_at,
        "last_triggered_at": row.last_triggered_at,
        "condition": {
            "metric_code": row.metric_code,
            "threshold": row.threshold,
            "direction": row.direction,
        },
    }


def _alert_event_dict(row: PortfolioAlertEvent) -> dict[str, object]:
    return {
        "event_id": row.id,
        "rule_id": row.rule_id,
        "portfolio_id": row.portfolio_id,
        "symbol": row.symbol,
        "triggered_at": row.triggered_at,
        "message": row.message,
        "evidence": row.evidence_json or {},
        "status": row.status,
        "severity": row.severity,
        "not_investment_advice": True,
    }


def _calendar_event_dict(row: PortfolioCalendarEvent) -> dict[str, object]:
    return {
        "id": row.id,
        "portfolio_id": row.portfolio_id,
        "symbol": row.symbol,
        "event_type": row.event_type,
        "title": row.title,
        "event_date": row.event_date,
        "source": row.source,
        "filing_id": row.filing_id,
        "report_run_id": row.report_run_id,
        "notes": row.notes,
        "severity": row.severity,
    }


def _apply_holding(row: PortfolioHolding, payload: dict[str, object]) -> None:
    if "symbol" in payload:
        row.symbol = str(payload["symbol"]).upper()
    for field in ("quantity", "cost_basis", "weight_override"):
        if field in payload:
            setattr(row, field, _float_or_none(payload.get(field)))
    for field in ("cost_currency", "position_date", "notes"):
        if field in payload:
            setattr(row, field, _str_or_none(payload.get(field)))
    row.source = "manual"


def _apply_watch_item(row: PortfolioWatchItem, payload: dict[str, object]) -> None:
    if "symbol" in payload:
        row.symbol = str(payload["symbol"]).upper()
    for field in ("thesis", "interest_level", "notes"):
        if field in payload:
            setattr(row, field, _str_or_none(payload.get(field)))
    if "tags" in payload:
        raw = payload.get("tags")
        row.tags = [str(item) for item in raw] if isinstance(raw, list) else []


def _str_or_none(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _upper_or_none(value: object) -> str | None:
    text = _str_or_none(value)
    return text.upper() if text else None


def _float_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, int) else None
