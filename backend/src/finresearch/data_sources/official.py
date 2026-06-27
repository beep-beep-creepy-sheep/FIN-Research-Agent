from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


SOURCE_TIERS = {
    "official",
    "regulator",
    "exchange",
    "issuer",
    "aggregator",
    "media",
    "community",
    "unknown",
}
VERIFIED_SOURCE_TIERS = {"official", "regulator", "exchange", "issuer"}


@dataclass(frozen=True)
class OfficialSourceDefinition:
    source_id: str
    source_name: str
    source_tier: str
    supported_markets: tuple[str, ...]
    supported_exchanges: tuple[str, ...]
    allowed_domains: tuple[str, ...]
    rate_limit_policy: dict[str, object] = field(default_factory=dict)
    listing_capability: bool = True
    download_capability: bool = True
    parse_capability: bool = True


@dataclass(frozen=True)
class SourceHealthResult:
    source_id: str
    enabled: bool
    configured: bool
    available: bool
    status: str
    latency_ms: int | None = None
    retry_after: str | None = None
    error_category: str | None = None


@dataclass(frozen=True)
class SourceCompanyIdentity:
    source_id: str
    symbol: str
    standard_symbol: str
    exchange: str
    market: str
    issuer_name: str | None = None
    external_issuer_id: str | None = None
    external_symbol: str | None = None
    listing_status: str | None = "active"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FilingCandidate:
    source_id: str
    source_document_id: str
    symbol: str
    exchange: str | None
    title: str
    filing_type: str | None
    document_type: str | None
    announcement_category: str | None
    publication_date: str | None
    report_period: str | None
    canonical_url: str
    download_url: str | None
    source_tier: str
    raw_metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FilingMetadata(FilingCandidate):
    period_start: str | None = None
    period_end: str | None = None
    published_at: str | None = None
    language: str | None = None
    content_type: str | None = None
    content_length: int | None = None


@dataclass(frozen=True)
class DownloadedArtifact:
    source_id: str
    source_document_id: str
    final_path: Path
    raw_metadata_path: Path
    sha256: str
    content_type: str
    content_length: int
    file_magic: str
    reused: bool = False


@dataclass(frozen=True)
class FilingSyncResult:
    source_id: str
    listed: int
    saved: int
    duplicates: int
    errors: list[dict[str, object]]


@dataclass(frozen=True)
class ParseResult:
    document_id: int
    filing_id: int | None
    status: str
    parser_version: str
    page_count: int
    chunks_created: int
    warnings: list[str] = field(default_factory=list)


class OfficialSourceAdapter(Protocol):
    definition: OfficialSourceDefinition

    @property
    def source_id(self) -> str: ...

    @property
    def source_name(self) -> str: ...

    @property
    def source_tier(self) -> str: ...

    def health_check(self) -> SourceHealthResult: ...

    def resolve_company(self, symbol: str) -> SourceCompanyIdentity: ...

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
    ) -> list[FilingCandidate]: ...

    def fetch_filing_metadata(self, candidate: FilingCandidate) -> FilingMetadata: ...

    def download_artifact(self, metadata: FilingMetadata) -> bytes: ...

    def normalize_filing(self, raw: dict[str, object]) -> FilingCandidate: ...


class FixtureOfficialSourceAdapter:
    definition: OfficialSourceDefinition

    def __init__(self, definition: OfficialSourceDefinition, fixture_items: list[dict[str, object]]) -> None:
        self.definition = definition
        self._fixture_items = fixture_items

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
        return SourceHealthResult(
            source_id=self.source_id,
            enabled=True,
            configured=True,
            available=True,
            status="fixture_verified",
            latency_ms=0,
        )

    def resolve_company(self, symbol: str) -> SourceCompanyIdentity:
        exchange = infer_cn_exchange(symbol)
        return SourceCompanyIdentity(
            source_id=self.source_id,
            symbol=symbol,
            standard_symbol=standardize_cn_symbol(symbol),
            exchange=exchange,
            market="CN-A",
            external_symbol=symbol.split(".")[0],
            issuer_name=None,
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
        normalized_symbol = symbol.split(".")[0]
        items: list[FilingCandidate] = []
        for raw in self._fixture_items:
            candidate = self.normalize_filing(raw)
            if candidate.symbol.split(".")[0] != normalized_symbol:
                continue
            if start_date and (candidate.publication_date or "") < start_date:
                continue
            if end_date and (candidate.publication_date or "") > end_date:
                continue
            if filing_type and candidate.filing_type != filing_type:
                continue
            if report_period and candidate.report_period != report_period:
                continue
            items.append(candidate)
        start = max(page - 1, 0) * limit
        return items[start : start + limit]

    def fetch_filing_metadata(self, candidate: FilingCandidate) -> FilingMetadata:
        return FilingMetadata(**candidate.__dict__)

    def download_artifact(self, metadata: FilingMetadata) -> bytes:
        title_text = f"{metadata.source_document_id} {metadata.title}"
        title = title_text.encode("latin1", errors="ignore") or metadata.source_document_id.encode("ascii", errors="ignore") or b"fixture filing"
        stream = b"BT /F1 12 Tf 72 720 Td (" + title[:80].replace(b"(", b"[").replace(b")", b"]") + b") Tj ET"
        objects = [
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
            b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
            b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj\n",
        ]
        content = b"%PDF-1.4\n"
        offsets = [0]
        for obj in objects:
            offsets.append(len(content))
            content += obj
        xref_start = len(content)
        content += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
        for offset in offsets[1:]:
            content += f"{offset:010d} 00000 n \n".encode("ascii")
        content += (
            b"trailer << /Size "
            + str(len(objects) + 1).encode("ascii")
            + b" /Root 1 0 R >>\nstartxref\n"
            + str(xref_start).encode("ascii")
            + b"\n%%EOF\n"
        )
        return content

    def normalize_filing(self, raw: dict[str, object]) -> FilingCandidate:
        source_document_id = str(raw.get("source_document_id") or raw.get("id") or "")
        if not source_document_id:
            raise ValueError("missing_source_document_id")
        symbol = str(raw.get("symbol") or "")
        if not symbol:
            raise ValueError("missing_symbol")
        canonical_url = str(raw.get("canonical_url") or raw.get("url") or "")
        if not canonical_url:
            raise ValueError("missing_source_url")
        return FilingCandidate(
            source_id=self.source_id,
            source_document_id=source_document_id,
            symbol=standardize_cn_symbol(symbol),
            exchange=str(raw.get("exchange") or infer_cn_exchange(symbol)),
            title=str(raw.get("title") or ""),
            filing_type=str(raw.get("filing_type") or "announcement"),
            document_type=str(raw.get("document_type") or "pdf"),
            announcement_category=str(raw.get("announcement_category") or "periodic_report"),
            publication_date=_string_or_none(raw.get("publication_date")),
            report_period=_string_or_none(raw.get("report_period")),
            canonical_url=canonical_url,
            download_url=_string_or_none(raw.get("download_url")) or canonical_url,
            source_tier=self.source_tier,
            raw_metadata=dict(raw),
        )


def standardize_cn_symbol(symbol: str) -> str:
    clean = symbol.strip().upper()
    if "." in clean:
        return clean
    exchange = infer_cn_exchange(clean)
    suffix = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(exchange, "CN")
    return f"{clean}.{suffix}"


def infer_cn_exchange(symbol: str) -> str:
    clean = symbol.strip().upper().split(".")[0]
    if symbol.upper().endswith(".SH") or clean.startswith(("6", "9")):
        return "SSE"
    if symbol.upper().endswith(".BJ") or clean.startswith(("8", "4")):
        return "BSE"
    if symbol.upper().endswith(".SZ") or clean.startswith(("0", "2", "3")):
        return "SZSE"
    return "UNKNOWN"


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
