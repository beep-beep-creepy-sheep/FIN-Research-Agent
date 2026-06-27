from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

import requests

from finresearch.data_sources.official import (
    FilingCandidate,
    FilingMetadata,
    OfficialSourceDefinition,
    SourceAdapterError,
    SourceCompanyIdentity,
    SourceHealthResult,
    infer_cn_exchange,
    standardize_cn_symbol,
)
from finresearch.settings import get_settings


CNINFO_QUERY_ENDPOINT = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DETAIL_ENDPOINT = "https://www.cninfo.com.cn/new/disclosure/detail"
CNINFO_STATIC_PREFIX = "https://static.cninfo.com.cn/"


class CNInfoLiveSourceAdapter:
    def __init__(self, definition: OfficialSourceDefinition) -> None:
        self.definition = definition
        self.settings = get_settings()

    @property
    def source_id(self) -> str:
        return self.definition.source_id

    @property
    def source_name(self) -> str:
        return self.definition.source_name

    @property
    def source_tier(self) -> str:
        return self.definition.source_tier

    def health_check(self) -> SourceHealthResult:
        if not self.settings.official_sources_enabled:
            return SourceHealthResult(
                source_id=self.source_id,
                enabled=False,
                configured=False,
                available=False,
                status="disabled",
            )
        started = perf_counter()
        try:
            self.list_filings(symbol="600519", page=1, limit=1)
        except SourceAdapterError as exc:
            return SourceHealthResult(
                source_id=self.source_id,
                enabled=True,
                configured=True,
                available=False,
                status=exc.status,
                latency_ms=int((perf_counter() - started) * 1000),
                retry_after=exc.retry_after,
                error_category=exc.error_type,
            )
        return SourceHealthResult(
            source_id=self.source_id,
            enabled=True,
            configured=True,
            available=True,
            status="live_available",
            latency_ms=int((perf_counter() - started) * 1000),
        )

    def resolve_company(self, symbol: str) -> SourceCompanyIdentity:
        clean = symbol.upper().split(".")[0]
        exchange = infer_cn_exchange(symbol)
        org_id = _cninfo_org_id(clean, exchange)
        return SourceCompanyIdentity(
            source_id=self.source_id,
            symbol=clean,
            standard_symbol=standardize_cn_symbol(symbol),
            exchange=exchange,
            market="CN-A",
            external_issuer_id=org_id,
            external_symbol=clean,
            listing_status="active",
            metadata={"live_adapter": "cninfo"},
        )

    def list_filings(
        self,
        *,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        filing_type: str | None = None,
        report_period: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> list[FilingCandidate]:
        clean = symbol.upper().split(".")[0]
        exchange = infer_cn_exchange(symbol)
        org_id = _cninfo_org_id(clean, exchange)
        se_date = f"{start_date or ''}~{end_date or ''}" if start_date or end_date else ""
        payload = {
            "stock": f"{clean},{org_id}",
            "tabName": "fulltext",
            "pageSize": str(min(max(limit, 1), 30)),
            "pageNum": str(max(page, 1)),
            "column": "sse" if exchange == "SSE" else "szse",
            "category": "",
            "plate": "",
            "seDate": se_date,
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        started = perf_counter()
        try:
            response = requests.post(
                CNINFO_QUERY_ENDPOINT,
                data=payload,
                headers=_headers(),
                timeout=(
                    self.settings.official_source_request_timeout_seconds,
                    self.settings.official_source_read_timeout_seconds,
                ),
            )
        except requests.Timeout as exc:
            raise SourceAdapterError(
                "cninfo_timeout",
                status="live_blocked",
                error_type="timeout",
                blocked_reason="network_timeout",
                endpoint=CNINFO_QUERY_ENDPOINT,
            ) from exc
        except requests.RequestException as exc:
            raise SourceAdapterError(
                "cninfo_network_error",
                status="live_blocked",
                error_type=type(exc).__name__,
                blocked_reason="network_error",
                endpoint=CNINFO_QUERY_ENDPOINT,
            ) from exc

        if response.status_code == 429:
            raise SourceAdapterError(
                "cninfo_rate_limited",
                status="rate_limited",
                error_type="http_429",
                retry_after=response.headers.get("Retry-After"),
                blocked_reason="rate_limited",
                endpoint=CNINFO_QUERY_ENDPOINT,
            )
        if response.status_code in {401, 403}:
            raise SourceAdapterError(
                "cninfo_blocked_by_anti_bot",
                status="live_blocked",
                error_type=f"http_{response.status_code}",
                blocked_reason="anti_bot_or_forbidden",
                endpoint=CNINFO_QUERY_ENDPOINT,
            )
        if response.status_code >= 500:
            raise SourceAdapterError(
                "cninfo_server_error",
                status="live_blocked",
                error_type=f"http_{response.status_code}",
                blocked_reason="source_unavailable",
                endpoint=CNINFO_QUERY_ENDPOINT,
            )

        content_type = response.headers.get("content-type", "")
        text = response.text[: 1024 * 1024]
        if "json" not in content_type.lower() and text.lstrip().startswith("<"):
            raise SourceAdapterError(
                "cninfo_non_json_response",
                status="source_changed",
                error_type="non_json_response",
                blocked_reason="html_error_page",
                endpoint=CNINFO_QUERY_ENDPOINT,
            )
        try:
            payload_json = response.json()
        except ValueError as exc:
            raise SourceAdapterError(
                "cninfo_json_parse_failed",
                status="source_changed",
                error_type="invalid_json",
                blocked_reason="source_contract_changed",
                endpoint=CNINFO_QUERY_ENDPOINT,
            ) from exc

        announcements = payload_json.get("announcements")
        if announcements is None:
            if payload_json.get("classifiedAnnouncements") is None:
                raise SourceAdapterError(
                    "cninfo_missing_announcements",
                    status="source_changed",
                    error_type="missing_announcements",
                    blocked_reason="source_contract_changed",
                    endpoint=CNINFO_QUERY_ENDPOINT,
                )
            announcements = []
        candidates = [self.normalize_filing(dict(item), clean, exchange) for item in announcements]
        if filing_type:
            candidates = [item for item in candidates if item.filing_type == filing_type]
        if report_period:
            candidates = [item for item in candidates if item.report_period == report_period]
        for candidate in candidates:
            candidate.raw_metadata["live_latency_ms"] = int((perf_counter() - started) * 1000)
            candidate.raw_metadata["request_endpoint"] = CNINFO_QUERY_ENDPOINT
        return candidates

    def fetch_filing_metadata(self, candidate: FilingCandidate) -> FilingMetadata:
        return FilingMetadata(**candidate.__dict__)

    def download_artifact(self, metadata: FilingMetadata) -> bytes:
        raise SourceAdapterError(
            "live_download_uses_artifact_download_service",
            status="error",
            error_type="unsupported_direct_download",
        )

    def normalize_filing(
        self,
        raw: dict[str, object],
        symbol: str | None = None,
        exchange: str | None = None,
    ) -> FilingCandidate:
        clean_symbol = symbol or str(raw.get("secCode") or raw.get("symbol") or "")
        clean_exchange = exchange or infer_cn_exchange(clean_symbol)
        announcement_id = str(raw.get("announcementId") or raw.get("id") or "")
        adjunct_url = str(raw.get("adjunctUrl") or "")
        title = _clean_title(str(raw.get("announcementTitle") or raw.get("title") or ""))
        if not announcement_id:
            raise SourceAdapterError(
                "cninfo_missing_announcement_id",
                status="source_changed",
                error_type="missing_source_document_id",
                blocked_reason="source_contract_changed",
                endpoint=CNINFO_QUERY_ENDPOINT,
            )
        if not title:
            raise SourceAdapterError(
                "cninfo_missing_title",
                status="source_changed",
                error_type="missing_title",
                blocked_reason="source_contract_changed",
                endpoint=CNINFO_QUERY_ENDPOINT,
            )
        download_url = CNINFO_STATIC_PREFIX + adjunct_url.lstrip("/") if adjunct_url else None
        canonical_url = f"{CNINFO_DETAIL_ENDPOINT}?stockCode={clean_symbol}&announcementId={announcement_id}"
        publication_date = _normalize_date(raw.get("announcementTime") or raw.get("publication_date"))
        return FilingCandidate(
            source_id=self.source_id,
            source_document_id=announcement_id,
            symbol=standardize_cn_symbol(clean_symbol),
            exchange=clean_exchange,
            title=title,
            filing_type=_infer_filing_type(title),
            document_type="pdf" if (download_url or "").lower().endswith(".pdf") else "html",
            announcement_category=str(raw.get("category") or raw.get("announcementType") or "announcement"),
            publication_date=publication_date,
            report_period=_infer_report_period(title, publication_date),
            canonical_url=canonical_url,
            download_url=download_url,
            source_tier=self.source_tier,
            raw_metadata={
                **raw,
                "request_endpoint": CNINFO_QUERY_ENDPOINT,
                "checked_at": datetime.now(UTC).isoformat(),
            },
        )


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "FinResearchAgent/0.1 official-source-smoke contact=local",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://www.cninfo.com.cn",
        "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    }


def _cninfo_org_id(symbol: str, exchange: str) -> str:
    if exchange == "SSE":
        return f"gssh0{symbol}"
    return f"gssz{symbol}"


def _clean_title(title: str) -> str:
    return title.replace("<em>", "").replace("</em>", "").strip()


def _normalize_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return datetime.fromtimestamp(float(value) / 1000, UTC).date().isoformat()
    text = str(value).strip()
    if not text:
        return None
    return text[:10]


def _infer_filing_type(title: str) -> str:
    if "年度报告" in title:
        return "annual_report"
    if "半年度报告" in title:
        return "semiannual_report"
    if "季度报告" in title:
        return "quarterly_report"
    return "announcement"


def _infer_report_period(title: str, publication_date: str | None) -> str | None:
    for year in range(2020, 2031):
        if str(year) in title:
            return str(year)
    return publication_date[:4] if publication_date else None
