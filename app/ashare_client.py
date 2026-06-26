from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import math
from typing import Any

from app.financial_store import infer_exchange
from app.models import CompanyRecord, FinancialFact, PriceRecord


class AShareDataError(RuntimeError):
    pass


METRIC_ALIASES: dict[str, tuple[str, str]] = {
    "营业总收入": ("revenue", "营业总收入"),
    "营业收入": ("revenue", "营业收入"),
    "TOTAL_OPERATE_INCOME": ("revenue", "营业总收入"),
    "OPERATE_INCOME": ("revenue", "营业收入"),
    "净利润": ("net_profit", "净利润"),
    "NETPROFIT": ("net_profit", "净利润"),
    "归属于母公司所有者的净利润": ("net_profit_parent", "归母净利润"),
    "PARENT_NETPROFIT": ("net_profit_parent", "归母净利润"),
    "经营活动产生的现金流量净额": ("operating_cash_flow", "经营现金流量净额"),
    "NETCASH_OPERATE": ("operating_cash_flow", "经营现金流量净额"),
    "资产总计": ("total_assets", "资产总计"),
    "TOTAL_ASSETS": ("total_assets", "资产总计"),
    "负债合计": ("total_liabilities", "负债合计"),
    "TOTAL_LIABILITIES": ("total_liabilities", "负债合计"),
    "所有者权益合计": ("total_equity", "所有者权益合计"),
    "TOTAL_EQUITY": ("total_equity", "所有者权益合计"),
    "归属于母公司所有者权益合计": ("equity_parent", "归母权益"),
    "TOTAL_PARENT_EQUITY": ("equity_parent", "归母权益"),
}


@dataclass(frozen=True)
class AShareDataClient:
    data_source: str = "akshare"

    def _akshare(self) -> Any:
        try:
            import akshare as ak  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AShareDataError(
                "AKShare is not installed. Install it with: pip install akshare"
            ) from exc
        return ak

    def fetch_company(self, symbol: str) -> CompanyRecord:
        ak = self._akshare()
        name: str | None = None
        industry: str | None = None
        try:
            spot = ak.stock_zh_a_spot_em()
            row = _first_matching_row(spot, ["代码"], symbol)
            if row:
                name = _string_value(row, ["名称"])
        except Exception:
            name = None

        try:
            info = ak.stock_individual_info_em(symbol=symbol)
            rows = _records(info)
            for row in rows:
                item = _string_value(row, ["item", "项目"])
                value = _string_value(row, ["value", "值"])
                if item in {"股票简称", "简称"} and value:
                    name = value
                if item in {"行业", "所属行业"} and value:
                    industry = value
        except Exception:
            industry = None

        return CompanyRecord(
            symbol=symbol,
            exchange=infer_exchange(symbol),
            company_name=name or symbol,
            industry=industry,
            currency="CNY",
            status="active",
        )

    def fetch_prices(self, symbol: str, years: int = 5, adjustment: str = "qfq") -> list[PriceRecord]:
        ak = self._akshare()
        start_year = datetime.now(UTC).year - years
        start_date = f"{start_year}0101"
        end_date = datetime.now(UTC).strftime("%Y%m%d")
        try:
            frame = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjustment,
            )
        except Exception as exc:
            raise AShareDataError(f"AKShare price fetch failed for {symbol}: {exc}") from exc

        retrieved_at = now_iso()
        prices: list[PriceRecord] = []
        for row in _records(frame):
            trade_date = _string_value(row, ["日期", "date"])
            if not trade_date:
                continue
            prices.append(
                PriceRecord(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=_number_value(row, ["开盘", "open"]),
                    high=_number_value(row, ["最高", "high"]),
                    low=_number_value(row, ["最低", "low"]),
                    close=_number_value(row, ["收盘", "close"]),
                    volume=_number_value(row, ["成交量", "volume"]),
                    amount=_number_value(row, ["成交额", "amount"]),
                    adjustment_type=adjustment or "none",
                    data_source=self.data_source,
                    retrieved_at=retrieved_at,
                )
            )
        return prices

    def fetch_financial_facts(self, symbol: str, years: int = 5) -> list[FinancialFact]:
        ak = self._akshare()
        facts: list[FinancialFact] = []
        sources = [
            ("balance_sheet", ak.stock_balance_sheet_by_report_em),
            ("profit_sheet", ak.stock_profit_sheet_by_report_em),
            ("cash_flow", _cash_flow_function(ak)),
        ]
        for statement_type, function in sources:
            if function is None:
                continue
            try:
                frame = function(symbol=_ak_symbol(symbol))
            except TypeError:
                frame = function(symbol=symbol)
            except Exception as exc:
                raise AShareDataError(
                    f"AKShare {statement_type} fetch failed for {symbol}: {exc}"
                ) from exc
            facts.extend(
                normalize_financial_rows(
                    _records(frame),
                    symbol=symbol,
                    years=years,
                    statement_type=statement_type,
                    data_source=self.data_source,
                )
            )
        return facts


def normalize_financial_rows(
    rows: list[dict[str, Any]],
    *,
    symbol: str,
    years: int,
    statement_type: str,
    data_source: str,
) -> list[FinancialFact]:
    retrieved_at = now_iso()
    facts: list[FinancialFact] = []
    for row in rows:
        period_end = _period_end(row)
        if not period_end:
            continue
        year = int(period_end[:4])
        if year < datetime.now(UTC).year - years:
            continue
        publication_date = _string_value(row, ["公告日期", "发布日期", "披露日期", "NOTICE_DATE"])
        seen_metric_codes: set[str] = set()
        for source_name, (metric_code, metric_name) in METRIC_ALIASES.items():
            if metric_code in seen_metric_codes:
                continue
            value = _number_value(row, [source_name])
            if value is None:
                continue
            seen_metric_codes.add(metric_code)
            facts.append(
                FinancialFact(
                    symbol=symbol,
                    metric_code=metric_code,
                    metric_name=metric_name,
                    value=value,
                    unit="元",
                    currency="CNY",
                    period_end=period_end,
                    publication_date=publication_date,
                    report_type=_report_type(period_end),
                    statement_type=statement_type,
                    is_consolidated=True,
                    source_text=source_name,
                    data_source=data_source,
                    retrieved_at=retrieved_at,
                )
            )
    return facts


def _records(frame: Any) -> list[dict[str, Any]]:
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    if isinstance(frame, list):
        return [dict(item) for item in frame]
    return []


def _first_matching_row(frame: Any, keys: list[str], value: str) -> dict[str, Any] | None:
    for row in _records(frame):
        if _string_value(row, keys) == value:
            return row
    return None


def _string_value(row: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return None


def _number_value(row: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(str(value).replace(",", ""))
            return number if math.isfinite(number) else None
        except ValueError:
            continue
    return None


def _period_end(row: dict[str, Any]) -> str | None:
    raw = _string_value(row, ["报告期", "截止日期", "报表日期", "REPORT_DATE", "date"])
    if not raw:
        return None
    text = raw[:10].replace("/", "-")
    if len(text) == 4:
        return f"{text}-12-31"
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def _report_type(period_end: str) -> str:
    if period_end.endswith("12-31"):
        return "annual"
    if period_end.endswith(("03-31", "06-30", "09-30")):
        return "quarterly"
    return "unknown"


def _ak_symbol(symbol: str) -> str:
    if symbol.startswith("6"):
        return f"SH{symbol}"
    if symbol.startswith(("0", "3")):
        return f"SZ{symbol}"
    if symbol.startswith(("4", "8")):
        return f"BJ{symbol}"
    return symbol


def _cash_flow_function(ak: Any) -> Any:
    for name in ("stock_cash_flow_sheet_by_report_em", "stock_cash_flow_sheet_by_yearly_em"):
        function = getattr(ak, name, None)
        if function is not None:
            return function
    return None


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
