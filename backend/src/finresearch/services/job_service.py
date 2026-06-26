from __future__ import annotations

from pathlib import Path

from finresearch.repositories.jobs import JobRepository
from finresearch.services.company_sync import SyncCompanyService
from finresearch.services.market_snapshot import MarketSnapshotService


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

    def get(self, job_id: int) -> dict[str, object] | None:
        return self.repository.get(job_id)

    def run_next(self) -> dict[str, object] | None:
        jobs = self.repository.list_queued(limit=1)
        if not jobs:
            return None
        job = jobs[0]
        job_id = int(job["id"])
        payload = dict(job["payload"])
        self.repository.update(job_id, status="running", progress=10, current_stage="syncing")
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
            self.repository.update(
                job_id,
                status="failed",
                progress=100,
                current_stage="failed",
                error_message=str(exc),
            )
        return self.repository.get(job_id)
