from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Response, status

from backend.services.job_service import (
    delete_favorite,
    list_jobs,
    save_favorite,
    update_favorite,
)


router = APIRouter(prefix="/api", tags=["favorites"])


class FavoritePayload(BaseModel):
    memo: str = ""
    status: str = "saved"


class FavoritePatch(BaseModel):
    memo: Optional[str] = None
    status: Optional[str] = None


@router.get("/favorites")
def read_favorites(status_filter: Optional[str] = Query(default=None, alias="status")):
    return {"items": list_jobs(favorite_only=True, status=status_filter)}


@router.post("/jobs/{job_id}/favorite")
def create_favorite(job_id: int, payload: FavoritePayload):
    try:
        return save_favorite(job_id, payload.memo, payload.status)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/favorites/{job_id}")
def patch_favorite(job_id: int, payload: FavoritePatch):
    try:
        return update_favorite(job_id, payload.memo, payload.status)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/jobs/{job_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(job_id: int):
    if not delete_favorite(job_id):
        raise HTTPException(status_code=404, detail="관심공고를 찾을 수 없습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
