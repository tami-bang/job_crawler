from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


KST = timezone(timedelta(hours=9))
KOREAN_WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")
DEFAULT_HISTORY_PATH = Path("frontend/public/crawl_history.json")


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid crawl history JSON: {path}") from exc
    if not isinstance(history, list):
        raise ValueError(f"crawl history must be a JSON array: {path}")
    return [entry for entry in history if isinstance(entry, dict)]


def record_crawl_history(
    new_jobs_count: int,
    total_jobs_count: int,
    *,
    path: str | Path = DEFAULT_HISTORY_PATH,
    crawled_at: datetime | None = None,
) -> dict[str, Any]:
    output_path = Path(path)
    now = (crawled_at or datetime.now(KST)).astimezone(KST)
    date = now.strftime("%Y.%m.%d")
    history = load_history(output_path)
    previous = next((entry for entry in history if entry.get("date") == date), None)
    daily_new_count = max(0, int(new_jobs_count))
    if previous:
        daily_new_count += max(0, int(previous.get("new_jobs_count", 0)))

    entry = {
        "date": date,
        "day_of_week": KOREAN_WEEKDAYS[now.weekday()],
        "new_jobs_count": daily_new_count,
        "total_jobs_count": max(0, int(total_jobs_count)),
        "crawled_at": now.strftime("%H:%M KST"),
    }
    merged = [entry, *(item for item in history if item.get("date") != date)]
    merged.sort(key=lambda item: str(item.get("date", "")), reverse=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return entry
