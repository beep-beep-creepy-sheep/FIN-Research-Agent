from __future__ import annotations

import json
from datetime import UTC, datetime
from time import perf_counter

from finresearch.data_sources.official import SourceAdapterError
from finresearch.data_sources.official_registry import OfficialSourceRegistry
from finresearch.settings import get_settings


SMOKE_SYMBOLS = {
    "cninfo": "600519",
    "sse": "600519",
    "szse": "000001",
    "bse": "430047",
    "sec_edgar": "AAPL",
}


def run_smoke() -> list[dict[str, object]]:
    settings = get_settings()
    registry = OfficialSourceRegistry()
    rows: list[dict[str, object]] = []
    for definition in registry.list_definitions():
        source_id = definition.source_id
        symbol = SMOKE_SYMBOLS.get(source_id, "600519")
        started = perf_counter()
        row: dict[str, object] = {
            "source_id": source_id,
            "mode": settings.official_source_mode,
            "symbol": symbol,
            "request_url": "not_implemented",
            "status": "NOT_CONFIGURED" if not settings.run_live_source_tests else "NOT_IMPLEMENTED",
            "listed_count": 0,
            "downloaded_count": 0,
            "parsed_count": 0,
            "latency_ms": 0,
            "error_type": None,
            "error_message": None,
            "blocked_reason": None,
            "checked_at": datetime.now(UTC).isoformat(),
        }
        if not settings.run_live_source_tests or settings.official_source_mode != "live":
            rows.append(row)
            continue
        try:
            adapter = registry.get_live_adapter(source_id)
            candidates = adapter.list_filings(symbol=symbol, page=1, limit=1)
            row.update(
                {
                    "request_url": candidates[0].raw_metadata.get("request_endpoint")
                    if candidates
                    else "https://www.cninfo.com.cn/new/hisAnnouncement/query",
                    "status": "PASS",
                    "listed_count": len(candidates),
                }
            )
        except SourceAdapterError as exc:
            row.update(
                {
                    "request_url": exc.endpoint or row["request_url"],
                    "status": _smoke_status(exc),
                    "error_type": exc.error_type,
                    "error_message": str(exc),
                    "blocked_reason": exc.blocked_reason,
                }
            )
        except Exception as exc:
            row.update(
                {
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
        row["latency_ms"] = int((perf_counter() - started) * 1000)
        row["checked_at"] = datetime.now(UTC).isoformat()
        rows.append(row)
    return rows


def _smoke_status(exc: SourceAdapterError) -> str:
    if exc.status == "rate_limited":
        return "RATE_LIMITED"
    if exc.blocked_reason in {"anti_bot_or_forbidden"}:
        return "BLOCKED_BY_ANTI_BOT"
    if exc.blocked_reason in {"network_error", "network_timeout", "source_unavailable"}:
        return "BLOCKED_BY_NETWORK"
    if exc.blocked_reason == "source_contract_changed":
        return "SOURCE_CHANGED"
    if exc.blocked_reason == "not_implemented":
        return "NOT_IMPLEMENTED"
    if exc.status == "not_configured":
        return "NOT_CONFIGURED"
    return "FAIL"


def main() -> None:
    print(json.dumps(run_smoke(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
