import os
from urllib.parse import quote

import requests


class MapConfigError(RuntimeError):
    pass


class MapLookupError(RuntimeError):
    pass


def is_map_configured() -> bool:
    return bool(get_naver_key_id(required=False) and get_naver_key(required=False))


def estimate_commute_time(origin: str, destination: str) -> dict:
    key_id = get_naver_key_id()
    key = get_naver_key()
    origin_point = geocode_address(origin, key_id, key)
    destination_point = geocode_address(destination, key_id, key)
    duration_ms = get_driving_duration_ms(origin_point, destination_point, key_id, key)
    minutes = max(1, round(duration_ms / 1000 / 60))
    return {
        "available": True,
        "duration_minutes": minutes,
        "label": format_duration(minutes),
        "map_url": build_naver_map_url(destination),
        "reason": None,
    }


def geocode_address(address: str, key_id: str, key: str) -> tuple[str, str]:
    response = requests.get(
        "https://maps.apigw.ntruss.com/map-geocode/v2/geocode",
        params={"query": address},
        headers=naver_headers(key_id, key),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    addresses = data.get("addresses") or []
    if not addresses:
        raise MapLookupError(f"주소를 찾을 수 없습니다: {address}")
    first = addresses[0]
    return str(first["x"]), str(first["y"])


def get_driving_duration_ms(
    origin_point: tuple[str, str],
    destination_point: tuple[str, str],
    key_id: str,
    key: str,
) -> int:
    response = requests.get(
        "https://maps.apigw.ntruss.com/map-direction/v1/driving",
        params={
            "start": ",".join(origin_point),
            "goal": ",".join(destination_point),
            "option": "traoptimal",
        },
        headers=naver_headers(key_id, key),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    routes = data.get("route", {}).get("traoptimal") or []
    if not routes:
        raise MapLookupError("경로를 찾을 수 없습니다.")
    return int(routes[0]["summary"]["duration"])


def naver_headers(key_id: str, key: str) -> dict:
    return {
        "X-NCP-APIGW-API-KEY-ID": key_id,
        "X-NCP-APIGW-API-KEY": key,
    }


def format_duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    return f"{hours:02d}시간 {rest:02d}분"


def build_naver_map_url(destination: str) -> str:
    return f"https://map.naver.com/p/search/{quote(destination)}"


def get_naver_key_id(required: bool = True) -> str:
    value = (
        os.getenv("NAVER_MAPS_CLIENT_ID")
        or os.getenv("NCP_MAPS_API_KEY_ID")
        or os.getenv("X_NCP_APIGW_API_KEY_ID")
    )
    if required and not value:
        raise MapConfigError("네이버지도 API Key ID가 설정되지 않았습니다.")
    return value or ""


def get_naver_key(required: bool = True) -> str:
    value = (
        os.getenv("NAVER_MAPS_CLIENT_SECRET")
        or os.getenv("NCP_MAPS_API_KEY")
        or os.getenv("X_NCP_APIGW_API_KEY")
    )
    if required and not value:
        raise MapConfigError("네이버지도 API Key가 설정되지 않았습니다.")
    return value or ""
