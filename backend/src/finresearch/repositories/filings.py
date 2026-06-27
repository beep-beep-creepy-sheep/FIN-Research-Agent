from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from finresearch.data_sources.official import FilingCandidate, SourceCompanyIdentity
from finresearch.database.models import Company, CompanySourceIdentifier, Filing
from finresearch.database.session import session_scope


class FilingRepository:
    def upsert_company_identity(self, identity: SourceCompanyIdentity) -> int:
        now = datetime.now(UTC).isoformat()
        with session_scope() as session:
            company = session.scalar(select(Company).where(Company.symbol == identity.standard_symbol))
            if company is None:
                company = Company(
                    symbol=identity.standard_symbol,
                    exchange=identity.exchange,
                    company_name=identity.issuer_name,
                    status=identity.listing_status,
                )
                session.add(company)
                session.flush()
            existing = session.scalar(
                select(CompanySourceIdentifier).where(
                    CompanySourceIdentifier.source_id == identity.source_id,
                    CompanySourceIdentifier.external_symbol == identity.external_symbol,
                    CompanySourceIdentifier.exchange == identity.exchange,
                )
            )
            if existing is None:
                existing = CompanySourceIdentifier(
                    company_id=company.id,
                    source_id=identity.source_id,
                    external_issuer_id=identity.external_issuer_id,
                    external_symbol=identity.external_symbol,
                    exchange=identity.exchange,
                    market=identity.market,
                    issuer_name=identity.issuer_name,
                    current_name=identity.issuer_name,
                    listing_status=identity.listing_status,
                    is_current=True,
                    meta=identity.metadata,
                    verified_at=now,
                )
                session.add(existing)
            else:
                existing.company_id = company.id
                existing.verified_at = now
                existing.meta = identity.metadata
            session.flush()
            return int(company.id)

    def upsert_candidate(self, candidate: FilingCandidate, company_id: int | None = None) -> tuple[int, bool]:
        now = datetime.now(UTC).isoformat()
        with session_scope() as session:
            filing = session.scalar(
                select(Filing).where(
                    Filing.source_id == candidate.source_id,
                    Filing.source_document_id == candidate.source_document_id,
                )
            )
            created = filing is None
            if filing is None:
                filing = Filing(
                    source_id=candidate.source_id,
                    source_document_id=candidate.source_document_id,
                    created_at=datetime.now(UTC),
                )
                session.add(filing)
            filing.company_id = company_id
            filing.symbol = candidate.symbol
            filing.exchange = candidate.exchange
            filing.title = candidate.title
            filing.filing_type = candidate.filing_type
            filing.document_type = candidate.document_type
            filing.announcement_category = candidate.announcement_category
            filing.publication_date = candidate.publication_date
            filing.report_period = candidate.report_period
            filing.canonical_url = candidate.canonical_url
            filing.source_url = candidate.canonical_url
            filing.download_url = candidate.download_url
            filing.source_tier = candidate.source_tier
            filing.verification_status = (
                "verified_source" if candidate.source_tier in {"official", "regulator", "exchange", "issuer"} else "unverified"
            )
            filing.download_status = filing.download_status or "pending"
            filing.parse_status = filing.parse_status or "pending"
            filing.retrieved_at = now
            filing.source_name = candidate.source_id
            session.flush()
            return int(filing.id), created

    def list(self, symbol: str | None = None, *, limit: int = 50, offset: int = 0) -> list[dict[str, object]]:
        with session_scope() as session:
            query = select(Filing).order_by(Filing.publication_date.desc().nullslast(), Filing.id.desc())
            if symbol:
                query = query.where(Filing.symbol.in_((symbol, _standardize(symbol))))
            rows = session.scalars(query.offset(offset).limit(limit)).all()
            return [_filing_dict(row) for row in rows]

    def get(self, filing_id: int) -> dict[str, object] | None:
        with session_scope() as session:
            filing = session.get(Filing, filing_id)
            return _filing_dict(filing) if filing else None

    def update_download(
        self,
        filing_id: int,
        *,
        local_path: str,
        raw_metadata_path: str,
        sha256: str,
        content_type: str,
        content_length: int,
        status: str = "downloaded",
    ) -> None:
        with session_scope() as session:
            filing = session.get(Filing, filing_id)
            if filing is None:
                return
            filing.local_path = local_path
            filing.raw_metadata_path = raw_metadata_path
            filing.sha256 = sha256
            filing.file_hash = sha256
            filing.content_type = content_type
            filing.content_length = content_length
            filing.download_status = status
            filing.last_attempt_at = datetime.now(UTC).isoformat()

    def update_parse_status(self, filing_id: int, status: str, error: str | None = None) -> None:
        with session_scope() as session:
            filing = session.get(Filing, filing_id)
            if filing is None:
                return
            filing.parse_status = status
            filing.error_message = error
            filing.last_attempt_at = datetime.now(UTC).isoformat()


def _filing_dict(row: Filing) -> dict[str, object]:
    return {
        "id": row.id,
        "company_id": row.company_id,
        "symbol": row.symbol,
        "exchange": row.exchange,
        "source_id": row.source_id,
        "source_document_id": row.source_document_id,
        "source_tier": row.source_tier,
        "verification_status": row.verification_status,
        "filing_type": row.filing_type,
        "document_type": row.document_type,
        "announcement_category": row.announcement_category,
        "title": row.title,
        "report_period": row.report_period,
        "publication_date": row.publication_date,
        "canonical_url": row.canonical_url,
        "download_url": row.download_url,
        "content_type": row.content_type,
        "content_length": row.content_length,
        "sha256": row.sha256 or row.file_hash,
        "download_status": row.download_status,
        "parse_status": row.parse_status,
        "retrieved_at": row.retrieved_at,
        "error_type": row.error_type,
        "error_message": row.error_message,
    }


def _standardize(symbol: str) -> str:
    clean = symbol.upper()
    if "." in clean:
        return clean
    if clean.startswith("6"):
        return f"{clean}.SH"
    if clean.startswith(("8", "4")):
        return f"{clean}.BJ"
    return f"{clean}.SZ"
