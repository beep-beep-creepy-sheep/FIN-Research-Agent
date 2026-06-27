from __future__ import annotations

from finresearch.data_sources.cninfo_live import CNInfoLiveSourceAdapter
from finresearch.data_sources.official import (
    FixtureOfficialSourceAdapter,
    OfficialSourceAdapter,
    OfficialSourceDefinition,
    SourceAdapterError,
)
from finresearch.settings import get_settings


CNINFO_DEFINITION = OfficialSourceDefinition(
    source_id="cninfo",
    source_name="CNINFO 巨潮资讯",
    source_tier="official",
    supported_markets=("CN-A",),
    supported_exchanges=("SSE", "SZSE", "BSE"),
    allowed_domains=("www.cninfo.com.cn", "static.cninfo.com.cn"),
    rate_limit_policy={"requests_per_second": 0.5, "respect_retry_after": True},
)
SSE_DEFINITION = OfficialSourceDefinition(
    source_id="sse",
    source_name="Shanghai Stock Exchange",
    source_tier="exchange",
    supported_markets=("CN-A",),
    supported_exchanges=("SSE",),
    allowed_domains=("www.sse.com.cn", "static.sse.com.cn"),
    rate_limit_policy={"requests_per_second": 0.5, "respect_retry_after": True},
)
SZSE_DEFINITION = OfficialSourceDefinition(
    source_id="szse",
    source_name="Shenzhen Stock Exchange",
    source_tier="exchange",
    supported_markets=("CN-A",),
    supported_exchanges=("SZSE",),
    allowed_domains=("www.szse.cn", "disc.static.szse.cn"),
    rate_limit_policy={"requests_per_second": 0.5, "respect_retry_after": True},
)
BSE_DEFINITION = OfficialSourceDefinition(
    source_id="bse",
    source_name="Beijing Stock Exchange",
    source_tier="exchange",
    supported_markets=("CN-A",),
    supported_exchanges=("BSE",),
    allowed_domains=("www.bse.cn",),
    rate_limit_policy={"requests_per_second": 0.3, "respect_retry_after": True},
)
SEC_DEFINITION = OfficialSourceDefinition(
    source_id="sec_edgar",
    source_name="SEC EDGAR",
    source_tier="regulator",
    supported_markets=("US",),
    supported_exchanges=("NYSE", "NASDAQ", "AMEX"),
    allowed_domains=("www.sec.gov", "sec.gov"),
    rate_limit_policy={"requests_per_second": 0.1, "respect_retry_after": True},
)

_FIXTURES = {
    "cninfo": [
        {
            "id": "cninfo-600519-2025-annual",
            "symbol": "600519",
            "exchange": "SSE",
            "title": "贵州茅台2025年年度报告",
            "filing_type": "annual_report",
            "document_type": "pdf",
            "announcement_category": "periodic_report",
            "publication_date": "2026-04-02",
            "report_period": "2025",
            "canonical_url": "https://www.cninfo.com.cn/new/disclosure/detail?docId=cninfo-600519-2025-annual",
            "download_url": "https://static.cninfo.com.cn/finalpage/2026-04-02/fixture.pdf",
        },
        {
            "id": "cninfo-600519-2025-annual-revision",
            "symbol": "600519",
            "exchange": "SSE",
            "title": "贵州茅台2025年年度报告修订版",
            "filing_type": "annual_report_revision",
            "document_type": "pdf",
            "announcement_category": "revision",
            "publication_date": "2026-04-10",
            "report_period": "2025",
            "canonical_url": "https://www.cninfo.com.cn/new/disclosure/detail?docId=cninfo-600519-2025-annual-revision",
            "download_url": "https://static.cninfo.com.cn/finalpage/2026-04-10/fixture.pdf",
        },
    ],
    "sse": [
        {
            "id": "sse-600519-2025-annual",
            "symbol": "600519",
            "exchange": "SSE",
            "title": "贵州茅台2025年年度报告",
            "filing_type": "annual_report",
            "document_type": "pdf",
            "announcement_category": "periodic_report",
            "publication_date": "2026-04-02",
            "report_period": "2025",
            "canonical_url": "https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/fixture.pdf",
            "download_url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/fixture.pdf",
        }
    ],
    "szse": [
        {
            "id": "szse-000001-2025-annual",
            "symbol": "000001",
            "exchange": "SZSE",
            "title": "平安银行2025年年度报告",
            "filing_type": "annual_report",
            "document_type": "pdf",
            "announcement_category": "periodic_report",
            "publication_date": "2026-03-15",
            "report_period": "2025",
            "canonical_url": "https://www.szse.cn/disclosure/listed/bulletinDetail/index.html?fixture",
            "download_url": "https://disc.static.szse.cn/download/disc/disk03/finalpage/fixture.pdf",
        }
    ],
    "bse": [
        {
            "id": "bse-430047-2025-annual",
            "symbol": "430047",
            "exchange": "BSE",
            "title": "北交所样例公司2025年年度报告",
            "filing_type": "annual_report",
            "document_type": "pdf",
            "announcement_category": "periodic_report",
            "publication_date": "2026-04-20",
            "report_period": "2025",
            "canonical_url": "https://www.bse.cn/disclosure/2026/fixture.pdf",
            "download_url": "https://www.bse.cn/disclosure/2026/fixture.pdf",
        }
    ],
    "sec_edgar": [],
}


class OfficialSourceRegistry:
    def __init__(self) -> None:
        self._definitions = {
            definition.source_id: definition
            for definition in [
                CNINFO_DEFINITION,
                SSE_DEFINITION,
                SZSE_DEFINITION,
                BSE_DEFINITION,
                SEC_DEFINITION,
            ]
        }

    def list_definitions(self) -> list[OfficialSourceDefinition]:
        return list(self._definitions.values())

    def get_definition(self, source_id: str) -> OfficialSourceDefinition | None:
        return self._definitions.get(source_id)

    def get_fixture_adapter(self, source_id: str) -> FixtureOfficialSourceAdapter:
        definition = self._definitions[source_id]
        return FixtureOfficialSourceAdapter(definition, _FIXTURES.get(source_id, []))

    def get_live_adapter(self, source_id: str) -> OfficialSourceAdapter:
        definition = self._definitions[source_id]
        if source_id == "cninfo":
            return CNInfoLiveSourceAdapter(definition)
        raise SourceAdapterError(
            f"live_adapter_not_implemented:{source_id}",
            status="not_configured",
            error_type="live_adapter_not_implemented",
            blocked_reason="not_implemented",
        )

    def get_adapter(self, source_id: str, mode: str | None = None) -> OfficialSourceAdapter:
        settings = get_settings()
        selected_mode = (mode or settings.official_source_mode).lower()
        if not settings.official_sources_enabled or selected_mode == "disabled":
            raise SourceAdapterError(
                "official_sources_disabled",
                status="disabled",
                error_type="official_sources_disabled",
            )
        if selected_mode == "live":
            return self.get_live_adapter(source_id)
        if selected_mode == "fixture":
            if settings.database_url.startswith("sqlite") or settings.allow_fixture_official_sources:
                return self.get_fixture_adapter(source_id)
            raise SourceAdapterError(
                "fixture_sources_not_allowed",
                status="not_configured",
                error_type="fixture_sources_not_allowed",
            )
        raise SourceAdapterError(
            f"unsupported_official_source_mode:{selected_mode}",
            status="not_configured",
            error_type="unsupported_official_source_mode",
        )

    def list_adapters(self, mode: str | None = None) -> list[OfficialSourceAdapter]:
        return [self.get_adapter(source_id, mode=mode) for source_id in self._definitions]


def source_coverage_matrix() -> list[dict[str, object]]:
    rows = []
    for definition in OfficialSourceRegistry().list_definitions():
        rows.append(
            {
                "source_id": definition.source_id,
                "source_name": definition.source_name,
                "enabled": True,
                "configured": True,
                "available": True,
                "source_tier": definition.source_tier,
                "supported_exchanges": list(definition.supported_exchanges),
                "company_resolution": True,
                "filing_listing": definition.listing_capability,
                "metadata_normalization": True,
                "pdf_download": definition.download_capability,
                "html_download": definition.source_id != "sec_edgar",
                "raw_archive": True,
                "parsing": definition.parse_capability,
                "page_lineage": True,
                "live_smoke": "NOT_RUN",
                "fixture_contract_tests": definition.source_id != "sec_edgar",
                "live_adapter": definition.source_id == "cninfo",
            }
        )
    return rows
