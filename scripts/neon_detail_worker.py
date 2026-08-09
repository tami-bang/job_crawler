import argparse
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import psycopg

from crawler.detail import parse_job_detail
from crawler.matcher import analyze_job, job_passes_hard_filters, load_preferences


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Referer": "https://www.jobkorea.co.kr/recruit/joblist?menucode=duty",
}


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


def fetch_detail(row):
    posting_id, source_job_id, title, company_name, raw_list_json = row
    url = f"https://www.jobkorea.co.kr/Recruit/GI_Read/{source_job_id}"
    last_error = None
    for attempt in range(3):
        try:
            with httpx.Client(headers=HEADERS, timeout=25, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                parsed = parse_job_detail(response.text)
                if not parsed.get("raw_detail_text"):
                    raise RuntimeError("empty parsed detail")
                return row, url, parsed, None
        except Exception as exc:
            last_error = exc
            time.sleep((2 ** attempt) + random.random())
    return row, url, None, last_error


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
    conn.commit()


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
    conn.commit()


def run(database_url, batch_size=200, workers=4, max_jobs=0):
    preferences = load_preferences()
    stats = {"claimed": 0, "success": 0, "failed": 0}
    with psycopg.connect(database_url) as conn:
        ensure_schema(conn)
        while max_jobs <= 0 or stats["claimed"] < max_jobs:
            size = min(batch_size, max_jobs - stats["claimed"]) if max_jobs > 0 else batch_size
            rows = claim_jobs(conn, size)
            if not rows:
                break
            stats["claimed"] += len(rows)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(fetch_detail, row) for row in rows]
                for future in as_completed(futures):
                    row, url, parsed, error = future.result()
                    if error:
                        save_failure(conn, row[0], error)
                        stats["failed"] += 1
                    else:
                        save_success(conn, row, url, parsed, preferences)
                        stats["success"] += 1
            print(json.dumps(stats, ensure_ascii=False), flush=True)
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-jobs", type=int, default=0)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    print(json.dumps(run(database_url, args.batch_size, args.workers, args.max_jobs), ensure_ascii=False))


if __name__ == "__main__":
    main()
