from __future__ import annotations

from dataclasses import dataclass, field

from finresearch.data_sources.official import FilingCandidate, FilingMetadata
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
