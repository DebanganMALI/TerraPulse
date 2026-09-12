import logging
import secrets
import threading
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, User
from app.db.session import session_scope
from app.errors import AppError
from app.schemas.analysis import AnalysisRequest
from app.schemas.common import ErrorCode, JobStatus, Provider
from app.services import store
from app.services.pipeline import get_pipeline

log = logging.getLogger("terrapulse")

ACTIVE = (JobStatus.queued.value, JobStatus.running.value)


def start_job(db: Session, user: User, aoi_id: str, provider: Provider) -> Job:
    running = db.scalar(
        select(Job).where(Job.username == user.username, Job.status.in_(ACTIVE))
    )
    if running is not None:
        raise AppError(
            409,
            ErrorCode.job_already_running,
            f"job {running.job_id} is still running",
        )

    job = Job(
        job_id=f"job_{secrets.token_hex(3)}",
        aoi_id=aoi_id,
        username=user.username,
        provider=provider.value,
        status=JobStatus.queued.value,
        progress=0,
    )
    db.add(job)
    db.commit()

    threading.Thread(
        target=_run, args=(job.job_id, aoi_id, provider), daemon=True
    ).start()
    return job


def get_job(db: Session, job_id: str) -> Job:
    job = db.scalar(select(Job).where(Job.job_id == job_id))
    if job is None:
        raise AppError(404, ErrorCode.job_not_found, f"unknown job: {job_id}")
    return job


def _set(job_id: str, **fields) -> None:
    with session_scope() as db:
        job = db.scalar(select(Job).where(Job.job_id == job_id))
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)


def _run(job_id: str, aoi_id: str, provider: Provider) -> None:
    """Runs off-request in a worker thread.

    Every failure path has to end with the job marked failed: an exception that
    escapes here would leave the UI polling a job that never finishes.
    """
    _set(
        job_id,
        status=JobStatus.running.value,
        started_at=datetime.now(UTC),
        stage="starting",
    )

    def on_progress(percent: int, stage: str) -> None:
        _set(job_id, progress=max(0, min(100, int(percent))), stage=stage)

    try:
        req = AnalysisRequest(aoi_id=aoi_id, provider=provider, job_id=job_id)
        result = get_pipeline()(req, on_progress)

        with session_scope() as db:
            counts = store.persist(db, result)

        _set(
            job_id,
            status=JobStatus.done.value,
            progress=100,
            stage="done",
            finished_at=datetime.now(UTC),
            n_events=counts["events"],
            n_risk_cells=counts["risk_cells"],
            n_alerts=counts["alerts"],
            warnings=result.warnings,
            model_info=result.model_info,
            overlays=result.overlays,
        )
    except Exception as exc:
        log.exception("analysis job %s failed", job_id)
        _set(
            job_id,
            status=JobStatus.failed.value,
            stage="failed",
            finished_at=datetime.now(UTC),
            error=f"{type(exc).__name__}: {exc}"[:800],
        )
