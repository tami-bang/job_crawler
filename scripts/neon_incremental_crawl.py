from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
import psycopg
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


KST = timezone(timedelta(hours=9))
API_URL = "https://www.jobkorea.co.kr/Recruit/Home/_GI_List/"
DEFAULT_PARTITION = "main_jobkorea"
DEVELOPER_DUTY_CODES = (
    "1000229,1000230,1000231,1000232,1000233,1000234,1000236,1000237,"
    "1000423,1000422,1000421,1000420,1000419,1000418,1000417,1000247,"
    "1000246,1000245,1000244,1000242"
)


class ApplicationPeriod(BaseModel):
    model_config = ConfigDict(extra="ignore")
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def normalize_datetime(cls, value):
        return parse_datetime(value)


class JobListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: str
    title: str
    company_name: str = Field(alias="companyName")
    created_at: datetime = Field(alias="createdAt")
    application_period: Optional[ApplicationPeriod] = Field(None, alias="applicationPeriod")
    career_range: Optional[str] = Field(None, alias="careerRange")
    employment_type_code_list: list[str] = Field(default_factory=list, alias="employmentTypeCodeList")
    area_code_list: list[str] = Field(default_factory=list, alias="areaCodeList")
    job_classification_or_industry: Optional[str] = Field(None, alias="jobClassificationOrIndustry")

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value):
        return str(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, value):
        parsed = parse_datetime(value)
        if parsed is None:
            raise ValueError("createdAt is required")
        return parsed

    def canonical_hash(self) -> str:
        period = self.application_period
        payload = {
            "title": self.title.strip(),
            "company_name": self.company_name.strip(),
            "career_range": self.career_range or "",
            "employment_types": sorted(self.employment_type_code_list),
            "area_codes": sorted(self.area_code_list),
            "application_period": {
                "start": period.start.isoformat() if period and period.start else None,
                "end": period.end.isoformat() if period and period.end else None,
            },
            "classification": self.job_classification_or_industry or "",
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def parse_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError(f"unsupported datetime: {value!r}")
    if value.tzinfo is None:
        value = value.replace(tzinfo=KST)
    return value.astimezone(KST)


def extract_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("API response must be a JSON object")
    for path in (("content",), ("data", "content"), ("data", "items"), ("items",)):
        value: Any = payload
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, list):
            return value
    raise ValueError("job list not found in API response")


def parse_relative_posted_at(text: str, now: Optional[datetime] = None) -> datetime:
    now = (now or datetime.now(KST)).astimezone(KST)
    normalized = " ".join(text.split())
    if "오늘" in normalized or "방금" in normalized:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    import re
    match = re.search(r"(\d+)\s*일\s*전", normalized)
    if match:
        return (now - timedelta(days=int(match.group(1)))).replace(hour=0, minute=0, second=0, microsecond=0)
    match = re.search(r"(\d+)\s*시간\s*전", normalized)
    if match:
        return (now - timedelta(hours=int(match.group(1)))).replace(minute=0, second=0, microsecond=0)
    match = re.search(r"(\d+)\s*분\s*전", normalized)
    if match:
        return (now - timedelta(minutes=int(match.group(1)))).replace(second=0, microsecond=0)
    match = re.search(r"(\d{1,2})/(\d{1,2})", normalized)
    if match:
        month, day = map(int, match.groups())
        year = now.year - (1 if month > now.month + 6 else 0)
        return datetime(year, month, day, tzinfo=KST)
    raise ValueError(f"unsupported posted date: {text!r}")


def parse_deadline(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    import re
    now = (now or datetime.now(KST)).astimezone(KST)
    match = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if not match:
        return None
    month, day = map(int, match.groups())
    year = now.year + (1 if month < now.month - 6 else 0)
    return datetime(year, month, day, 23, 59, 59, tzinfo=KST)


def parse_job_list_html(html: str, now: Optional[datetime] = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select("tr.devloopArea[data-gno]"):
        source_job_id = (row.get("data-gno") or "").strip()
        title_link = row.select_one("td.tplTit strong a[href*='/Recruit/GI_Read/']")
        company_link = row.select_one("td.tplCo > a.link")
        posted_node = row.select_one("td.odd .time")
        if not source_job_id or not title_link or not company_link or not posted_node:
            continue
        cells = [node.get_text(" ", strip=True) for node in row.select("td.tplTit p.etc span.cell")]
        deadline_text = row.select_one("td.odd .date")
        detail_path = title_link.get("href", "")
        item = {
            "id": source_job_id,
            "title": title_link.get("title") or title_link.get_text(" ", strip=True),
            "companyName": company_link.get_text(" ", strip=True),
            "createdAt": parse_relative_posted_at(posted_node.get_text(" ", strip=True), now),
            "applicationPeriod": {
                "end": parse_deadline(deadline_text.get_text(" ", strip=True), now) if deadline_text else None,
            },
            "careerRange": cells[0] if len(cells) > 0 else None,
            "education": cells[1] if len(cells) > 1 else None,
            "areaCodeList": [cells[2]] if len(cells) > 2 and cells[2] else [],
            "employmentTypeCodeList": [cells[3]] if len(cells) > 3 and cells[3] else [],
            "jobClassificationOrIndustry": (row.select_one("td.tplTit p.dsc") or row).get_text(" ", strip=True),
            "detailUrl": f"https://www.jobkorea.co.kr{detail_path}" if detail_path.startswith("/") else detail_path,
            "postedText": posted_node.get_text(" ", strip=True),
            "deadlineText": deadline_text.get_text(" ", strip=True) if deadline_text else "",
        }
        items.append(item)
    return items


def load_request_payload() -> dict[str, Any]:
    raw = os.environ.get("JOBKOREA_REQUEST_PAYLOAD_JSON")
    if raw:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("JOBKOREA_REQUEST_PAYLOAD_JSON must be an object")
        return payload
    return {
        "isDefault": "true",
        "condition[duty]": DEVELOPER_DUTY_CODES,
        "condition[menucode]": "",
        "page": "1",
        "direct": "0",
        "order": "20",
        "pagesize": "40",
        "tabindex": "0",
        "onePick": "0",
        "confirm": "0",
        "profile": "0",
    }


def upsert_job(cur, item: JobListItem, raw_item: dict[str, Any]) -> tuple[str, int]:
    stable_key = f"jobkorea:{item.id}"
    content_hash = item.canonical_hash()
    cur.execute(
        "SELECT id, list_content_hash FROM job_postings WHERE source = %s AND source_job_id = %s FOR UPDATE",
        ("jobkorea", item.id),
    )
    existing = cur.fetchone()
    if existing is None:
        cur.execute(
            """
            INSERT INTO job_postings (
                source, source_job_id, stable_key, title, company_name,
                source_posted_at, list_content_hash, raw_list_json, last_seen_at
            ) VALUES ('jobkorea', %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
            """,
            (item.id, stable_key, item.title, item.company_name, item.created_at, content_hash,
             json.dumps(raw_item, ensure_ascii=False, default=str)),
        )
        return "NEW", cur.fetchone()[0]

    posting_id, previous_hash = existing
    state = "CHANGED" if previous_hash != content_hash else "UNCHANGED"
    cur.execute(
        """
        UPDATE job_postings SET stable_key = %s, title = %s, company_name = %s,
            source_posted_at = %s, list_content_hash = %s, raw_list_json = %s,
            status = 'ACTIVE', last_seen_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (stable_key, item.title, item.company_name, item.created_at, content_hash,
         json.dumps(raw_item, ensure_ascii=False, default=str), posting_id),
    )
    return state, posting_id


def enqueue_detail(cur, posting_id: int, reason: str) -> None:
    cur.execute(
        """
        INSERT INTO detail_fetch_queue (job_posting_id, priority, status, reason)
        VALUES (%s, 0, 'QUEUED', %s)
        ON CONFLICT (job_posting_id) DO UPDATE SET
            status = CASE WHEN detail_fetch_queue.status = 'PROCESSING' THEN 'PROCESSING' ELSE 'QUEUED' END,
            reason = EXCLUDED.reason, next_attempt_at = NOW(), updated_at = NOW()
        """,
        (posting_id, reason),
    )


def upsert_page(conn, items: list[JobListItem], raw_items: list[dict[str, Any]]) -> dict[str, int]:
    source_ids = [item.id for item in items]
    with conn.cursor() as cur:
        cur.execute(
            "SELECT source_job_id, list_content_hash FROM job_postings WHERE source = 'jobkorea' AND source_job_id = ANY(%s)",
            (source_ids,),
        )
        previous_hashes = dict(cur.fetchall())

    states = {}
    with conn.pipeline(), conn.cursor() as cur:
        for item, raw_item in zip(items, raw_items):
            content_hash = item.canonical_hash()
            previous_hash = previous_hashes.get(item.id)
            state = "NEW" if previous_hash is None else ("CHANGED" if previous_hash != content_hash else "UNCHANGED")
            states[item.id] = state
            cur.execute(
                """
                INSERT INTO job_postings (
                    source, source_job_id, stable_key, title, company_name,
                    source_posted_at, list_content_hash, raw_list_json, last_seen_at
                ) VALUES ('jobkorea', %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (source, source_job_id) DO UPDATE SET
                    stable_key = EXCLUDED.stable_key, title = EXCLUDED.title,
                    company_name = EXCLUDED.company_name, source_posted_at = EXCLUDED.source_posted_at,
                    list_content_hash = EXCLUDED.list_content_hash, raw_list_json = EXCLUDED.raw_list_json,
                    status = 'ACTIVE', last_seen_at = NOW(), updated_at = NOW()
                """,
                (item.id, f"jobkorea:{item.id}", item.title, item.company_name, item.created_at,
                 content_hash, json.dumps(raw_item, ensure_ascii=False, default=str)),
            )

    changed_ids = [source_id for source_id, state in states.items() if state != "UNCHANGED"]
    if changed_ids:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_job_id, id FROM job_postings WHERE source = 'jobkorea' AND source_job_id = ANY(%s)",
                (changed_ids,),
            )
            posting_ids = dict(cur.fetchall())
        with conn.pipeline(), conn.cursor() as cur:
            for source_id in changed_ids:
                enqueue_detail(cur, posting_ids[source_id], states[source_id])
    return states


async def run_incremental_crawl(database_url: str, partition_key: str = DEFAULT_PARTITION) -> dict[str, int]:
    base_payload = load_request_payload()
    stats = {"pages": 0, "seen": 0, "new": 0, "changed": 0}
    observed_max = None
    completed_page = 0
    consecutive_old_unchanged = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://www.jobkorea.co.kr/recruit/joblist?menucode=duty",
        "X-Requested-With": "XMLHttpRequest",
    }

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO crawl_partitions (partition_key, request_payload_json, last_run_status)
                VALUES (%s, %s, 'RUNNING')
                ON CONFLICT (partition_key) DO UPDATE SET
                    request_payload_json = EXCLUDED.request_payload_json,
                    last_run_status = 'RUNNING', updated_at = NOW()
                RETURNING last_successful_watermark
                """,
                (partition_key, json.dumps(base_payload, ensure_ascii=False)),
            )
            previous_watermark = cur.fetchone()[0]
            conn.commit()
        watermark = previous_watermark - timedelta(days=3) if previous_watermark else None

        try:
            async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
                previous_page_ids = None
                max_pages = int(os.environ.get("JOBKOREA_MAX_PAGES", "500"))
                start_page = int(os.environ.get("JOBKOREA_START_PAGE", "1"))
                request_delay = float(os.environ.get("JOBKOREA_REQUEST_DELAY", "0.8"))
                for page in range(start_page, max_pages + 1):
                    payload = {**base_payload, "page": str(page)}
                    for attempt in range(5):
                        response = await client.post(API_URL, data=payload)
                        if response.status_code not in (429, 500, 502, 503, 504):
                            break
                        if attempt == 4:
                            response.raise_for_status()
                        await asyncio.sleep((2 ** attempt) + (page % 7) / 10)
                    response.raise_for_status()
                    raw_items = parse_job_list_html(response.text)
                    if not raw_items:
                        if page == start_page:
                            raise RuntimeError("first page contained no recognizable job rows")
                        break
                    page_ids = tuple(item["id"] for item in raw_items)
                    if page_ids == previous_page_ids:
                        raise RuntimeError(f"pagination did not advance on page {page}")
                    previous_page_ids = page_ids
                    try:
                        items = [JobListItem.model_validate(raw) for raw in raw_items]
                    except ValidationError as exc:
                        Path("data/quarantine").mkdir(parents=True, exist_ok=True)
                        Path(f"data/quarantine/{partition_key}-page-{page}.html").write_text(
                            response.text, encoding="utf-8"
                        )
                        raise RuntimeError(f"schema validation failed on page {page}: {exc}") from exc

                    changes = 0
                    states = upsert_page(conn, items, raw_items)
                    for item in items:
                        state = states[item.id]
                        stats["seen"] += 1
                        if state != "UNCHANGED":
                            stats[state.lower()] += 1
                            changes += 1
                        observed_max = max(observed_max, item.created_at) if observed_max else item.created_at
                    completed_page = page
                    stats["pages"] += 1
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE crawl_partitions SET last_completed_page = %s, last_job_count = %s, updated_at = NOW() WHERE partition_key = %s",
                            (page, stats["seen"], partition_key),
                        )
                    conn.commit()

                    page_is_old = watermark is not None and max(item.created_at for item in items) < watermark
                    consecutive_old_unchanged = consecutive_old_unchanged + 1 if page_is_old and changes == 0 else 0
                    if consecutive_old_unchanged >= 3:
                        break
                    await asyncio.sleep(request_delay)
        except Exception:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE crawl_partitions SET last_run_status = 'FAILED', updated_at = NOW() WHERE partition_key = %s",
                    (partition_key,),
                )
            conn.commit()
            raise

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE crawl_partitions SET last_successful_watermark = COALESCE(%s, last_successful_watermark),
                    last_completed_page = %s, last_run_status = 'SUCCESS', last_job_count = %s, updated_at = NOW()
                WHERE partition_key = %s
                """,
                (observed_max, completed_page, stats["seen"], partition_key),
            )
        conn.commit()
    return stats


def export_static_json(database_url: str, output: str) -> int:
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, source_job_id, stable_key, title, company_name, source_posted_at, raw_list_json
            FROM job_postings WHERE status = 'ACTIVE' ORDER BY source_posted_at DESC
            """
        )
        rows = cur.fetchall()
    data = [{
        "id": row[0], "source": row[1], "source_job_id": row[2], "stable_key": row[3],
        "title": row[4], "company_name": row[5], "posted_at": row[6].isoformat(),
        "raw": json.loads(row[7]) if row[7] else {},
    } for row in rows]
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("crawl", "export", "crawl-and-export"))
    parser.add_argument("--output", default="frontend/public/static_jobs.json")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    if args.command in ("crawl", "crawl-and-export"):
        print(json.dumps(asyncio.run(run_incremental_crawl(database_url)), ensure_ascii=False))
    if args.command in ("export", "crawl-and-export"):
        print(f"exported={export_static_json(database_url, args.output)}")


if __name__ == "__main__":
    main()
