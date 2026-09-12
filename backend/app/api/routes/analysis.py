from fastapi import APIRouter, Request, Response

from app.db.models import Job
from app.schemas.analysis import AnalysisRunRequest, JobOut
from app.schemas.common import JobStatus
from app.security.deps import AnalystUser, CurrentUser, DbDep
from app.security.limiter import limiter
from app.services import aoi as aoi_service
from app.services import audit, jobs

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _out(job: Job) -> JobOut:
    return JobOut(
        job_id=job.job_id,
        aoi_id=job.aoi_id,
        status=JobStatus(job.status),
        progress=job.progress,
        stage=job.stage,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        counts={
            "events": job.n_events,
            "risk_cells": job.n_risk_cells,
            "alerts": job.n_alerts,
        },
    )


@router.post("/run", response_model=JobOut, status_code=202)
@limiter.limit("10/minute")
def run(
    request: Request,
    response: Response,
    body: AnalysisRunRequest,
    db: DbDep,
    user: AnalystUser,
) -> JobOut:
    aoi_service.get_aoi(body.aoi_id)
    job = jobs.start_job(db, user, body.aoi_id, body.provider)
    audit.record(db, request, "analysis_run", username=user.username, target=body.aoi_id)
    return _out(job)


@router.get("/{job_id}", response_model=JobOut)
def status(job_id: str, db: DbDep, user: CurrentUser) -> JobOut:
    return _out(jobs.get_job(db, job_id))
