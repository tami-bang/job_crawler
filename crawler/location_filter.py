import re


ALLOWED_LOCATION_PREFIXES = ("서울", "서울특별시", "경기", "경기도", "인천", "인천광역시")
OUTSIDE_LOCATION_NAMES = (
    "부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남",
    "전북", "전남", "경북", "경남", "제주", "해외",
)


def is_capital_area_location(value):
    """Return True only for unambiguous Seoul/Gyeonggi/Incheon workplaces."""
    if isinstance(value, (list, tuple, set)):
        text = "\n".join(str(item or "").strip() for item in value if str(item or "").strip())
    else:
        text = str(value or "").strip()
    if not text:
        return True

    starts_in_allowed_area = any(
        re.search(rf"(^|[\n,/·])\s*{re.escape(prefix)}(?=\s|전체|$)", text)
        for prefix in ALLOWED_LOCATION_PREFIXES
    )
    if not starts_in_allowed_area:
        return False

    return not any(
        re.search(rf"(^|[\n,/·])\s*{re.escape(location)}(?=시|도|\s|전체|$)", text)
        for location in OUTSIDE_LOCATION_NAMES
    )
