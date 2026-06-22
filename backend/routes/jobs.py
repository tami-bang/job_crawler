from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.services.job_service import get_job, list_jobs


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def read_jobs(
    search: Optional[str] = None,
    favorite: bool = False,
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"items": list_jobs(search, favorite, status, limit)}


@router.get("/{job_id}")
def read_job(job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="채용공고를 찾을 수 없습니다.")
    return job
