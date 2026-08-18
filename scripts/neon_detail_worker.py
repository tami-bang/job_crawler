import argparse
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from crawler.detail import parse_job_detail
from crawler.matcher import analyze_job, job_passes_hard_filters, load_preferences
from scripts.jobkorea_http import DETAIL_HEADERS


HEADERS = DETAIL_HEADERS

RETRYABLE_STATUS_CODES = {403, 408, 425, 429, 500, 502, 503, 504}
WAF_MARKERS = (
    "access denied", "captcha", "cloudflare", "forbidden", "request blocked",
    "비정상적인 접근", "서비스 이용이 제한", "접근이 제한",
)


class DetailResponseError(RuntimeError):
    """A successful HTTP response that is not a usable JobKorea detail page."""


def response_diagnostics(response):
    if response is None:
        return "response=none"
    normalized = re.sub(r"\s+", " ", response.text or "").strip()
    body_hint = normalized[:240].replace("::", ": :") or "<empty>"
    lowered = normalized.lower()
    markers = [marker for marker in WAF_MARKERS if marker in lowered]
    content_type = response.headers.get("content-type", "unknown").split(";", 1)[0]
    return (
        f"status={response.status_code} url={response.url} content_type={content_type} "
        f"body_length={len(response.content)} waf_markers={markers or ['none']} "
        f"body_hint={body_hint!r}"
    )


def exception_diagnostics(exc, response=None):
    error_text = re.sub(r"\s+", " ", str(exc)).strip()
    if isinstance(exc, DetailResponseError):
        return f"{type(exc).__name__}: {error_text}"
    error_response = exc.response if isinstance(exc, httpx.HTTPStatusError) else response
    return f"{type(exc).__name__}: {error_text}; {response_diagnostics(error_response)}"


class RequestRateLimiter:
    """Keep concurrent workers from sending bursty requests to JobKorea."""

    def __init__(self, delay_seconds):
        self.delay_seconds = max(0.0, delay_seconds)
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def wait(self):
        with self._lock:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self.delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining + random.uniform(0.1, 0.4))
            self._last_request_at = time.monotonic()


def ensure_schema(conn):
    schema_path = os.path.join(os.path.dirname(__file__), "..", "sql", "neon_incremental_schema.sql")
    with open(schema_path, encoding="utf-8") as file, conn.cursor() as cur:
        cur.execute(file.read())
    conn.commit()


def claim_jobs(conn, limit):
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH candidates AS (
                SELECT q.job_posting_id
                FROM detail_fetch_queue q
                WHERE (q.status = 'QUEUED' AND q.next_attempt_at <= NOW())
                   OR (q.status = 'PROCESSING' AND q.lease_until < NOW())
                ORDER BY q.priority DESC, q.created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            UPDATE detail_fetch_queue q
            SET status = 'PROCESSING', lease_until = NOW() + INTERVAL '10 minutes',
                attempted_at = NOW(), updated_at = NOW()
            FROM candidates c
            WHERE q.job_posting_id = c.job_posting_id
            RETURNING q.job_posting_id
            """,
            (limit,),
        )
        posting_ids = [row[0] for row in cur.fetchall()]
        if not posting_ids:
            conn.commit()
            return []
        cur.execute(
            """
            SELECT id, source_job_id, title, company_name, raw_list_json
            FROM job_postings WHERE id = ANY(%s)
            """,
            (posting_ids,),
        )
        rows = cur.fetchall()
    conn.commit()
    return rows


def fetch_detail(row, client, rate_limiter, max_attempts):
    posting_id, source_job_id, title, company_name, raw_list_json = row
    url = f"https://www.jobkorea.co.kr/Recruit/GI_Read/{source_job_id}"
    last_error = None
    for attempt in range(max_attempts):
        response = None
        try:
            rate_limiter.wait()
            response = client.get(url)
            response.raise_for_status()
            parsed = parse_job_detail(response.text)
            detail_text = parsed.get("raw_detail_text") or ""
            if not parsed.get("has_core_content") or len(detail_text) < 120:
                raise DetailResponseError(
                    f"invalid parsed detail: source={parsed.get('body_source')} "
                    f"detail_length={len(detail_text)}; {response_diagnostics(response)}"
                )
            return row, url, parsed, None
        except Exception as exc:
            last_error = exc
            retryable = isinstance(exc, (httpx.RequestError, RuntimeError))
            if isinstance(exc, httpx.HTTPStatusError):
                retryable = exc.response.status_code in RETRYABLE_STATUS_CODES
            diagnostics = exception_diagnostics(exc, response)
            if not retryable or attempt == max_attempts - 1:
                print(
                    f"::warning::JobKorea detail attempt {attempt + 1}/{max_attempts} "
                    f"failed for {source_job_id}: {diagnostics}; no retries remaining",
                    flush=True,
                )
                break
            delay = min(30.0, 2 ** attempt) + random.uniform(0.25, 1.25)
            print(
                f"::warning::JobKorea detail attempt {attempt + 1}/{max_attempts} "
                f"failed for {source_job_id}: {diagnostics}; retrying in {delay:.1f}s",
                flush=True,
            )
            time.sleep(delay)
    return row, url, None, last_error


def release_network_batch(conn, rows, error):
    posting_ids = [row[0] for row in rows]
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE detail_fetch_queue SET status='QUEUED', lease_until=NULL,
                next_attempt_at=NOW() + INTERVAL '30 minutes', last_error=%s, updated_at=NOW()
            WHERE job_posting_id = ANY(%s)
            """,
            (str(error)[:2000], posting_ids),
        )
    conn.commit()


def build_match_job(row, parsed):
    posting_id, _source_job_id, title, _company_name, raw_list_json = row
    raw = json.loads(raw_list_json or "{}")
    return {
        "id": posting_id,
        "title": title,
        "location": parsed.get("location") or " ".join(raw.get("areaCodeList") or []),
        "career": parsed.get("career") or raw.get("careerRange") or "",
        "education": parsed.get("education") or raw.get("education") or "",
        "employment_type": parsed.get("employment_type") or " ".join(raw.get("employmentTypeCodeList") or []),
        "summary_text": raw.get("jobClassificationOrIndustry") or "",
        "description_text": parsed.get("description_text") or "",
        "main_tasks": parsed.get("main_tasks") or "",
        "qualifications": parsed.get("qualifications") or "",
        "preferred_conditions": parsed.get("preferred_conditions") or "",
        "benefits": parsed.get("benefits") or "",
        "skill_candidates": parsed.get("skill_candidates") or "",
        "detail_status": "success",
    }


def save_success(conn, row, url, parsed, preferences):
    job = build_match_job(row, parsed)
    analysis = analyze_job(job, preferences) if job_passes_hard_filters(job, preferences) else {
        "raw_score": 0, "match_score": 0, "recommendation_level": "filtered",
        "matched_keywords": [], "positive_reasons": [], "negative_reasons": ["필수 조건에서 제외됨"],
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE job_postings SET detail_url=%s, location=%s, career=%s, education=%s,
                employment_type=%s, deadline=%s, deadline_date=%s, description_text=%s,
                raw_detail_text=%s, main_tasks=%s, qualifications=%s, preferred_conditions=%s,
                benefits=%s, skill_candidates=%s, detail_status='success', detail_collected_at=NOW(),
                raw_score=%s, match_score=%s, recommendation_level=%s, matched_keywords_json=%s,
                positive_reasons_json=%s, negative_reasons_json=%s, updated_at=NOW()
            WHERE id=%s
            """,
            (url, job["location"], job["career"], job["education"], job["employment_type"],
             parsed.get("deadline"), parsed.get("deadline_date"), job["description_text"],
             parsed.get("raw_detail_text"), job["main_tasks"], job["qualifications"],
             job["preferred_conditions"], job["benefits"], job["skill_candidates"],
             analysis["raw_score"], analysis["match_score"], analysis["recommendation_level"],
             json.dumps(analysis["matched_keywords"], ensure_ascii=False),
             json.dumps(analysis["positive_reasons"], ensure_ascii=False),
             json.dumps(analysis["negative_reasons"], ensure_ascii=False), row[0]),
        )
        cur.execute(
            "UPDATE detail_fetch_queue SET status='SUCCESS', lease_until=NULL, last_error=NULL, updated_at=NOW() WHERE job_posting_id=%s",
            (row[0],),
        )


def save_failure(conn, posting_id, error):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE detail_fetch_queue SET retry_count=retry_count+1,
                status=CASE WHEN retry_count+1 >= 3 THEN 'FAILED' ELSE 'QUEUED' END,
                next_attempt_at=NOW() + (INTERVAL '5 minutes' * POWER(2, retry_count)),
                lease_until=NULL, last_error=%s, updated_at=NOW()
            WHERE job_posting_id=%s
            """,
            (str(error)[:2000], posting_id),
        )
        cur.execute("UPDATE job_postings SET detail_status='failed', updated_at=NOW() WHERE id=%s", (posting_id,))


def run(database_url, batch_size=20, workers=2, max_jobs=0):
    preferences = load_preferences()
    stats = {"claimed": 0, "success": 0, "failed": 0}
    with psycopg.connect(database_url) as conn:
        ensure_schema(conn)
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
        limits = httpx.Limits(max_connections=workers, max_keepalive_connections=workers)
        request_delay = float(os.environ.get("JOBKOREA_DETAIL_REQUEST_DELAY", "1.2"))
        max_attempts = max(1, int(os.environ.get("JOBKOREA_DETAIL_MAX_ATTEMPTS", "5")))
        rate_limiter = RequestRateLimiter(request_delay)
        with httpx.Client(headers=HEADERS.copy(), timeout=timeout, limits=limits, follow_redirects=True) as client:
            try:
                warmup = client.get("https://www.jobkorea.co.kr/recruit/joblist?menucode=duty")
                warmup.raise_for_status()
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                stats["network_error_skipped"] = 1
                print(
                    f"::warning::JobKorea detail connection failed; continuing with existing "
                    f"Neon data: {exception_diagnostics(exc, locals().get('warmup'))}",
                    flush=True,
                )
                return stats
            while max_jobs <= 0 or stats["claimed"] < max_jobs:
                size = min(batch_size, max_jobs - stats["claimed"]) if max_jobs > 0 else batch_size
                rows = claim_jobs(conn, size)
                if not rows:
                    break
                stats["claimed"] += len(rows)
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = [
                        executor.submit(fetch_detail, row, client, rate_limiter, max_attempts)
                        for row in rows
                    ]
                    results = [future.result() for future in as_completed(futures)]
                    errors = [result[3] for result in results if result[3] is not None]
                    if len(errors) == len(rows):
                        release_network_batch(conn, rows, errors[0])
                        stats["network_error_skipped"] = len(rows)
                        print(
                            "::warning::All detail requests in the batch failed; released leases "
                            "and continuing with existing Neon data",
                            flush=True,
                        )
                        return stats
                    try:
                        for row, url, parsed, error in results:
                            if error:
                                save_failure(conn, row[0], error)
                                stats["failed"] += 1
                            else:
                                save_success(conn, row, url, parsed, preferences)
                                stats["success"] += 1
                        conn.commit()
                    except Exception:
                        conn.rollback()
                        raise
                print(json.dumps(stats, ensure_ascii=False), flush=True)
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-jobs", type=int, default=0)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    print(json.dumps(run(database_url, args.batch_size, args.workers, args.max_jobs), ensure_ascii=False))


if __name__ == "__main__":
    main()
