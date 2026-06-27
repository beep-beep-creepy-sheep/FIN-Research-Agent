from __future__ import annotations

from dataclasses import dataclass, field

from finresearch.data_sources.official import (
    FilingCandidate,
    FilingMetadata,
    FixtureOfficialSourceAdapter,
    SourceAdapterError,
)
from finresearch.data_sources.official_registry import OfficialSourceRegistry
from finresearch.repositories.data_quality import DataQualityRepository
from finresearch.repositories.filings import FilingRepository
from finresearch.services.artifact_download import ArtifactDownloadService
from finresearch.services.filing_document_parser import FilingDocumentParser


@dataclass
class OfficialFilingSyncSummary:
    symbol: str
    sources_requested: list[str]
    listed: int = 0
    saved: int = 0
    duplicates: int = 0
    downloaded: int = 0
    parsed: int = 0
    errors: list[dict[str, object]] = field(default_factory=list)
    filing_ids: list[int] = field(default_factory=list)


class OfficialFilingService:
    def __init__(self) -> None:
        self.registry = OfficialSourceRegistry()
        self.repository = FilingRepository()
        self.quality = DataQualityRepository()

    def sync(
        self,
        symbol: str,
        *,
        source_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        download: bool = True,
        parse: bool = True,
    ) -> dict[str, object]:
        selected = source_ids or ["cninfo", "sse", "szse", "bse"]
        summary = OfficialFilingSyncSummary(symbol=symbol, sources_requested=selected)
        for source_id in selected:
            definition = self.registry.get_definition(source_id)
            if definition is None:
                summary.errors.append({"source_id": source_id, "error_type": "source_not_registered"})
                continue
            adapter = self.registry.get_adapter(source_id)
            try:
                identity = adapter.resolve_company(symbol)
                company_id = self.repository.upsert_company_identity(identity)
                candidates = adapter.list_filings(symbol=symbol, start_date=start_date, end_date=end_date)
                summary.listed += len(candidates)
                for candidate in candidates:
                    filing_id, created = self.repository.upsert_candidate(candidate, company_id)
                    summary.filing_ids.append(filing_id)
                    if created:
                        summary.saved += 1
                    else:
                        summary.duplicates += 1
                    self._quality_checks(candidate, filing_id)
                    if download:
                        metadata = adapter.fetch_filing_metadata(candidate)
                        artifact = ArtifactDownloadService().archive_bytes(
                            metadata,
                            adapter.download_artifact(metadata),
                            allowed_domains=definition.allowed_domains,
                            content_type=metadata.content_type or "application/pdf",
                        )
                        self.repository.update_download(
                            filing_id,
                            local_path=str(artifact.final_path),
                            raw_metadata_path=str(artifact.raw_metadata_path),
                            sha256=artifact.sha256,
                            content_type=artifact.content_type,
                            content_length=artifact.content_length,
                        )
                        summary.downloaded += 1
                    if parse:
                        parsed = FilingDocumentParser().parse_filing(filing_id)
                        if str(parsed["status"]).startswith("parsed"):
                            summary.parsed += 1
                        elif parsed["status"] == "ocr_required":
                            self.quality.upsert_issue(
                                issue_type="ocr_required",
                                severity="medium",
                                entity_type="filing",
                                entity_id=str(filing_id),
                                symbol=candidate.symbol,
                                source_id=source_id,
                                details=parsed,
                            )
            except Exception as exc:
                summary.errors.append(
                    {"source_id": source_id, "error_type": type(exc).__name__, "message": str(exc)}
                )
                self.quality.upsert_issue(
                    issue_type="source_unavailable",
                    severity="medium",
                    entity_type="source",
                    entity_id=source_id,
                    symbol=symbol,
                    source_id=source_id,
                    details={"message": str(exc)},
                )
        return summary.__dict__

    def download_filing(self, filing_id: int) -> dict[str, object]:
        filing = self.repository.get_internal(filing_id)
        if filing is None:
            raise ValueError("filing_not_found")
        source_id = str(filing.get("source_id") or "")
        definition = self.registry.get_definition(source_id)
        if definition is None:
            raise ValueError("source_not_registered")
        metadata = self._metadata_from_filing(filing)
        try:
            adapter = self.registry.get_adapter(source_id)
            if isinstance(adapter, FixtureOfficialSourceAdapter):
                artifact = ArtifactDownloadService().archive_bytes(
                    metadata,
                    adapter.download_artifact(metadata),
                    allowed_domains=definition.allowed_domains,
                    content_type=metadata.content_type or "application/pdf",
                )
            else:
                artifact = ArtifactDownloadService().download_from_url(
                    metadata,
                    allowed_domains=definition.allowed_domains,
                )
            self.repository.update_download(
                filing_id,
                local_path=str(artifact.final_path),
                raw_metadata_path=str(artifact.raw_metadata_path),
                sha256=artifact.sha256,
                content_type=artifact.content_type,
                content_length=artifact.content_length,
            )
            return {
                "filing_id": filing_id,
                "status": "downloaded",
                "sha256": artifact.sha256,
                "content_type": artifact.content_type,
                "content_length": artifact.content_length,
                "reused": artifact.reused,
            }
        except Exception as exc:
            error_type = getattr(exc, "error_type", type(exc).__name__)
            self.repository.update_download_failure(
                filing_id,
                error_type=str(error_type),
                error_message=str(exc),
            )
            issue_type = _download_issue_type(exc)
            self.quality.upsert_issue(
                issue_type=issue_type,
                severity="medium",
                entity_type="filing",
                entity_id=str(filing_id),
                symbol=str(filing.get("symbol") or ""),
                source_id=source_id,
                details={"message": str(exc), "error_type": str(error_type)},
            )
            raise

    def retry_filing(self, filing_id: int) -> dict[str, object]:
        filing = self.repository.get_internal(filing_id)
        if filing is None:
            raise ValueError("filing_not_found")
        download_status = str(filing.get("download_status") or "")
        parse_status = str(filing.get("parse_status") or "")
        if download_status == "failed" or not filing.get("local_path"):
            return self.download_filing(filing_id)
        if parse_status in {"failed", "parsed_with_warnings", "ocr_required", "pending"}:
            return FilingDocumentParser().parse_filing(filing_id)
        return {"filing_id": filing_id, "status": "no_retry_needed"}

    def _quality_checks(self, candidate: FilingCandidate | FilingMetadata, filing_id: int) -> None:
        if not candidate.publication_date:
            self.quality.upsert_issue(
                issue_type="missing_publication_date",
                severity="medium",
                entity_type="filing",
                entity_id=str(filing_id),
                symbol=candidate.symbol,
                source_id=candidate.source_id,
            )
        if not candidate.report_period:
            self.quality.upsert_issue(
                issue_type="missing_report_period",
                severity="low",
                entity_type="filing",
                entity_id=str(filing_id),
                symbol=candidate.symbol,
                source_id=candidate.source_id,
            )
        if not candidate.canonical_url:
            self.quality.upsert_issue(
                issue_type="missing_source_url",
                severity="high",
                entity_type="filing",
                entity_id=str(filing_id),
                symbol=candidate.symbol,
                source_id=candidate.source_id,
            )

    def _metadata_from_filing(self, filing: dict[str, object]) -> FilingMetadata:
        return FilingMetadata(
            source_id=str(filing.get("source_id") or ""),
            source_document_id=str(filing.get("source_document_id") or filing.get("id") or ""),
            symbol=str(filing.get("symbol") or ""),
            exchange=str(filing.get("exchange") or ""),
            title=str(filing.get("title") or ""),
            filing_type=_optional_str(filing.get("filing_type")),
            document_type=_optional_str(filing.get("document_type")) or "pdf",
            announcement_category=_optional_str(filing.get("announcement_category")),
            publication_date=_optional_str(filing.get("publication_date")),
            report_period=_optional_str(filing.get("report_period")),
            canonical_url=str(filing.get("canonical_url") or filing.get("download_url") or ""),
            download_url=_optional_str(filing.get("download_url")),
            source_tier=str(filing.get("source_tier") or "unknown"),
            raw_metadata={"filing_id": filing.get("id"), "retried_from_database": True},
            period_start=_optional_str(filing.get("period_start")),
            period_end=_optional_str(filing.get("period_end")),
            published_at=_optional_str(filing.get("published_at")),
            language=_optional_str(filing.get("language")),
            content_type=_optional_str(filing.get("content_type")),
            content_length=_optional_int(filing.get("content_length")),
        )


def _download_issue_type(exc: Exception) -> str:
    if isinstance(exc, SourceAdapterError) and exc.status == "rate_limited":
        return "source_unavailable"
    message = str(exc)
    if "invalid_pdf" in message or "html_error_page" in message:
        return "invalid_pdf"
    if "rate" in message.lower():
        return "source_unavailable"
    return "download_failed"


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
