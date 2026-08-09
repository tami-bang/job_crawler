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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


KST = timezone(timedelta(hours=9))
API_URL = "https://www.jobkorea.co.kr/Search/api/display/v2/jobs"
DEFAULT_PARTITION = "main_jobkorea"


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


def load_request_payload() -> dict[str, Any]:
    raw = os.environ.get("JOBKOREA_REQUEST_PAYLOAD_JSON")
    if raw:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("JOBKOREA_REQUEST_PAYLOAD_JSON must be an object")
        return payload
    return {"pageSize": 20, "page": 0, "sortProperty": "2", "sortDirection": "DESC", "deviceType": "PC"}


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


async def run_incremental_crawl(database_url: str, partition_key: str = DEFAULT_PARTITION) -> dict[str, int]:
    base_payload = load_request_payload()
    stats = {"pages": 0, "seen": 0, "new": 0, "changed": 0}
    observed_max = None
    completed_page = 0
    consecutive_old_unchanged = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": "https://www.jobkorea.co.kr/Search/",
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
        watermark = (previous_watermark or datetime.now(KST) - timedelta(days=30)) - timedelta(days=3)

        try:
            async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
                for page in range(100):
                    payload = {**base_payload, "page": page}
                    response = await client.post(API_URL, json=payload)
                    response.raise_for_status()
                    raw_items = extract_items(response.json())
                    if not raw_items:
                        break
                    try:
                        items = [JobListItem.model_validate(raw) for raw in raw_items]
                    except ValidationError as exc:
                        Path("data/quarantine").mkdir(parents=True, exist_ok=True)
                        Path(f"data/quarantine/{partition_key}-page-{page}.json").write_text(
                            json.dumps(response.json(), ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        raise RuntimeError(f"schema validation failed on page {page}: {exc}") from exc

                    changes = 0
                    with conn.cursor() as cur:
                        for item, raw_item in zip(items, raw_items):
                            state, posting_id = upsert_job(cur, item, raw_item)
                            stats["seen"] += 1
                            if state != "UNCHANGED":
                                stats[state.lower()] += 1
                                changes += 1
                                enqueue_detail(cur, posting_id, state)
                            observed_max = max(observed_max, item.created_at) if observed_max else item.created_at
                        completed_page = page
                        stats["pages"] += 1
                    conn.commit()

                    page_is_old = max(item.created_at for item in items) < watermark
                    consecutive_old_unchanged = consecutive_old_unchanged + 1 if page_is_old and changes == 0 else 0
                    if consecutive_old_unchanged >= 3:
                        break
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
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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
