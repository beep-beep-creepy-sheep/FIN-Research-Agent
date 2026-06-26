from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from finresearch.database.models import Job
from finresearch.database.session import session_scope


class JobRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def create(self, job_type: str, payload: dict[str, object]) -> dict[str, object]:
        with session_scope() as session:
            job = Job(job_type=job_type, status="queued", payload=payload, current_stage="queued")
            session.add(job)
            session.flush()
            return _job_dict(job)

    def find_active(self, job_type: str, payload: dict[str, object]) -> dict[str, object] | None:
        with session_scope() as session:
            jobs = session.scalars(
                select(Job)
                .where(Job.job_type == job_type, Job.status.in_(("queued", "running")))
                .order_by(Job.id.desc())
            ).all()
            for job in jobs:
                if _same_payload(job.payload or {}, payload):
                    data = _job_dict(job)
                    data["reused"] = True
                    return data
        return None

    def find_recent_completed(
        self, job_type: str, payload: dict[str, object], *, within_minutes: int = 10
    ) -> dict[str, object] | None:
        cutoff = datetime.now(UTC) - timedelta(minutes=within_minutes)
        with session_scope() as session:
            jobs = session.scalars(
                select(Job)
                .where(Job.job_type == job_type, Job.status == "completed")
                .order_by(Job.id.desc())
                .limit(20)
            ).all()
            for job in jobs:
                completed_at = job.completed_at
                if completed_at is None:
                    continue
                if completed_at.tzinfo is None:
                    completed_at = completed_at.replace(tzinfo=UTC)
                if completed_at < cutoff:
                    continue
                if _same_payload(job.payload or {}, payload):
                    data = _job_dict(job)
                    data["reused"] = True
                    data["fresh"] = True
                    return data
        return None

    def get(self, job_id: int) -> dict[str, object] | None:
        with session_scope() as session:
            job = session.get(Job, job_id)
            return _job_dict(job) if job else None

    def list_queued(self, limit: int = 1) -> list[dict[str, object]]:
        with session_scope() as session:
            jobs = session.scalars(
                select(Job).where(Job.status == "queued").order_by(Job.id).limit(limit)
            ).all()
            return [_job_dict(job) for job in jobs]

    def update(
        self,
        job_id: int,
        *,
        status: str,
        progress: int,
        current_stage: str,
        result: dict[str, object] | None = None,
        error_message: str | None = None,
    ) -> None:
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            job.status = status
            job.progress = progress
            job.current_stage = current_stage
            if result is not None:
                job.result = result
            job.error_message = error_message
            if job.started_at is None:
                job.started_at = datetime.now(UTC)
            if status in {"completed", "failed", "cancelled"}:
                job.completed_at = datetime.now(UTC)


def _job_dict(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "payload": job.payload,
        "result": job.result,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def _same_payload(left: dict[str, object], right: dict[str, object]) -> bool:
    return str(left.get("symbol", "")).upper() == str(right.get("symbol", "")).upper() and int(
        left.get("years", 5)
    ) == int(right.get("years", 5))
