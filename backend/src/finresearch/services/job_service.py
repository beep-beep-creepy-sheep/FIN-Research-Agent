from __future__ import annotations

from pathlib import Path

from finresearch.repositories.jobs import JobRepository
from finresearch.services.company_sync import SyncCompanyService
from finresearch.services.filing_document_parser import FilingDocumentParser
from finresearch.services.market_snapshot import MarketSnapshotService
from finresearch.services.official_filings import OfficialFilingService
from finresearch.services.research_service import ResearchService


class JobService:
    def __init__(self, library_path: Path) -> None:
        self.library_path = library_path
        self.repository = JobRepository(library_path)

    def create_sync_job(self, symbol: str, years: int = 5) -> dict[str, object]:
        payload = {"symbol": symbol.upper(), "years": years}
        active = self.repository.find_active("sync_company", payload)
        if active:
            return active
        recent = self.repository.find_recent_completed("sync_company", payload)
        if recent:
            return recent
        return self.repository.create("sync_company", payload)

    def create_market_snapshot_job(self, market: str = "CN") -> dict[str, object]:
        payload = {"market": market.upper()}
        active = self.repository.find_active("market_snapshot", payload)
        if active:
            return active
        recent = self.repository.find_recent_completed("market_snapshot", payload)
        if recent:
            return recent
        return self.repository.create("market_snapshot", payload)

    def create_official_filing_sync_job(
        self,
        symbol: str,
        *,
        source_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        download: bool = True,
        parse: bool = True,
    ) -> dict[str, object]:
        payload = {
            "symbol": symbol.upper(),
            "source_ids": source_ids,
            "start_date": start_date,
            "end_date": end_date,
            "download": download,
            "parse": parse,
        }
        active = self.repository.find_active("sync_official_filings", payload)
        if active:
            return active
        return self.repository.create("sync_official_filings", payload)

    def create_filing_job(self, job_type: str, filing_id: int) -> dict[str, object]:
        if job_type not in {"download_filing", "parse_filing", "reparse_document", "retry_filing"}:
            raise ValueError(f"unsupported_job_type:{job_type}")
        return self.repository.create(job_type, {"filing_id": filing_id})

    def create_research_job(
        self,
        *,
        research_run_id: int,
        symbol: str,
        years: int = 5,
        as_of_date: str | None = None,
    ) -> dict[str, object]:
        payload = {
            "research_run_id": research_run_id,
            "symbol": symbol.upper(),
            "years": years,
            "as_of_date": as_of_date,
        }
        return self.repository.create("research_run", payload)

    def get(self, job_id: int) -> dict[str, object] | None:
        return self.repository.get(job_id)

    def run_next(self) -> dict[str, object] | None:
        jobs = self.repository.list_queued(limit=1)
        if not jobs:
            return None
        job = jobs[0]
        job_id = int(job["id"])
        payload = dict(job["payload"])
        first_stage = "syncing" if job["job_type"] == "sync_company" else "starting"
        self.repository.update(job_id, status="running", progress=10, current_stage=first_stage)
        try:
            if job["job_type"] == "sync_company":
                symbol = str(payload["symbol"])
                years = int(payload.get("years", 5))
                result = SyncCompanyService(self.library_path).execute(symbol, years=years).__dict__
            elif job["job_type"] == "market_snapshot":
                self.repository.update(
                    job_id,
                    status="running",
                    progress=50,
                    current_stage="building_market_snapshot",
                )
                market = str(payload.get("market", "CN"))
                result = MarketSnapshotService().generate(market).__dict__
            elif job["job_type"] == "sync_official_filings":
                self.repository.update(
                    job_id,
                    status="running",
                    progress=35,
                    current_stage="listing_filings",
                )
                result = OfficialFilingService().sync(
                    str(payload["symbol"]),
                    source_ids=payload.get("source_ids"),
                    start_date=payload.get("start_date"),
                    end_date=payload.get("end_date"),
                    download=bool(payload.get("download", True)),
                    parse=bool(payload.get("parse", True)),
                )
            elif job["job_type"] in {"parse_filing", "reparse_document"}:
                self.repository.update(
                    job_id,
                    status="running",
                    progress=60,
                    current_stage="parsing_documents",
                )
                result = FilingDocumentParser().parse_filing(int(payload["filing_id"]))
            elif job["job_type"] == "download_filing":
                self.repository.update(
                    job_id,
                    status="running",
                    progress=45,
                    current_stage="downloading_artifacts",
                )
                result = OfficialFilingService().download_filing(int(payload["filing_id"]))
            elif job["job_type"] == "retry_filing":
                self.repository.update(
                    job_id,
                    status="running",
                    progress=45,
                    current_stage="retrying_filing",
                )
                result = OfficialFilingService().retry_filing(int(payload["filing_id"]))
            elif job["job_type"] == "research_run":
                run_id = int(payload["research_run_id"])
                ResearchService(self.library_path).research_repo.mark_running(run_id)
                self.repository.update(
                    job_id,
                    status="running",
                    progress=25,
                    current_stage="research_collecting_sources",
                )
                result = ResearchService(self.library_path).create_structured_run(
                    str(payload["symbol"]),
                    years=int(payload.get("years", 5)),
                    as_of_date=payload.get("as_of_date"),
                    run_id=run_id,
                )
            else:
                raise ValueError(f"unsupported_job_type:{job['job_type']}")
            self.repository.update(
                job_id,
                status="completed",
                progress=100,
                current_stage="completed",
                result=result,
                error_message=None,
            )
        except Exception as exc:
            payload = dict(job["payload"])
            if job["job_type"] == "research_run" and payload.get("research_run_id") is not None:
                ResearchService(self.library_path).research_repo.mark_failed(
                    int(payload["research_run_id"]), str(exc)
                )
            self.repository.update(
                job_id,
                status="failed",
                progress=100,
                current_stage="failed",
                error_message=str(exc),
                error_type=type(exc).__name__,
                retryable=True,
            )
        return self.repository.get(job_id)
