from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from backend.services.map_service import (
    MapConfigError,
    MapLookupError,
    build_naver_map_url,
    estimate_commute_time,
    is_map_configured,
)


router = APIRouter(prefix="/api/maps", tags=["maps"])


class CommutePayload(BaseModel):
    origin: str
    destination: str


@router.get("/status")
def map_status():
    return {"ready": is_map_configured()}


@router.post("/commute-time")
def commute_time(payload: CommutePayload):
    if not payload.origin.strip() or not payload.destination.strip():
        raise HTTPException(status_code=422, detail="출발지와 도착지를 입력해주세요.")
    try:
        return estimate_commute_time(payload.origin.strip(), payload.destination.strip())
    except MapConfigError as exc:
        return {
            "available": False,
            "duration_minutes": None,
            "label": "지도 API 설정 필요",
            "map_url": build_naver_map_url(payload.destination),
            "reason": str(exc),
        }
    except (MapLookupError, Exception) as exc:
        return {
            "available": False,
            "duration_minutes": None,
            "label": "계산 실패",
            "map_url": build_naver_map_url(payload.destination),
            "reason": str(exc),
        }
