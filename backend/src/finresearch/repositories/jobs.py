from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect, select, text

from finresearch.database.models import Job
from finresearch.database.session import session_scope


class JobRepository:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with session_scope() as session:
            bind = session.get_bind()
            columns = {column["name"] for column in inspect(bind).get_columns("jobs")}
            dialect = bind.dialect.name
            text_type = "TEXT"
            bool_type = "BOOLEAN" if dialect != "sqlite" else "BOOLEAN"
            timestamp_type = "TIMESTAMP" if dialect != "sqlite" else "DATETIME"
            additions = {
                "error_type": f"{text_type}",
                "failed_at": f"{timestamp_type}",
                "retryable": f"{bool_type}",
            }
            for name, definition in additions.items():
                if name not in columns:
                    session.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {definition}"))

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
        error_type: str | None = None,
        retryable: bool | None = None,
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
            job.error_type = error_type
            job.error_message = error_message
            job.retryable = retryable
            if job.started_at is None:
                job.started_at = datetime.now(UTC)
            if status in {"completed", "failed", "cancelled"}:
                job.completed_at = datetime.now(UTC)
            if status == "failed":
                job.failed_at = datetime.now(UTC)


def _job_dict(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "payload": job.payload,
        "result": job.result,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "error_type": job.error_type,
        "error_message": job.error_message,
        "failed_at": job.failed_at.isoformat() if job.failed_at else None,
        "retryable": job.retryable,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def _same_payload(left: dict[str, object], right: dict[str, object]) -> bool:
    if "symbol" not in left and "symbol" not in right:
        return left == right
    return str(left.get("symbol", "")).upper() == str(right.get("symbol", "")).upper() and int(
        left.get("years", 5)
    ) == int(right.get("years", 5))
