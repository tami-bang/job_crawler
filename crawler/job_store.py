# crawler/job_store.py
import hashlib
import json

from crawler.database import DEFAULT_DB_PATH, get_connection, init_database
from crawler.parser import is_always_open_deadline, normalize_deadline_date, normalize_url


def save_job_list_items(jobs, crawl_run_id, db_path=DEFAULT_DB_PATH, source="jobkorea"):
    init_database(db_path)

    result = {
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
    }

    with get_connection(db_path) as conn:
        for job in jobs:
            if not _is_valid_job(job):
                result["skipped"] += 1
                continue

            company_id = upsert_company(conn, job, source)
            status = upsert_job_posting(conn, job, company_id, crawl_run_id, source)
            result[status] += 1

    return result


def save_raw_list_page(conn, crawl_run_id, url, html, source="jobkorea"):
    conn.execute(
        """
        INSERT INTO raw_pages (
            crawl_run_id, source, page_type, url, raw_content, content_hash
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (crawl_run_id, source, "list_page", url, html, _hash_text(html)),
    )


def upsert_company(conn, job, source):
    company_name = _clean_text(job.get("company")) or "Unknown"
    company_url = normalize_url(job.get("company_url", ""))
    source_company_key = company_url or _normalize_key(company_name)

    conn.execute(
        """
        INSERT INTO companies (
            source, source_company_key, name, company_url
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source, source_company_key)
        DO UPDATE SET
            name = excluded.name,
            company_url = COALESCE(NULLIF(excluded.company_url, ''), companies.company_url),
            last_seen_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (source, source_company_key, company_name, company_url),
    )

    row = conn.execute(
        """
        SELECT id
        FROM companies
        WHERE source = ? AND source_company_key = ?
        """,
        (source, source_company_key),
    ).fetchone()
    return row["id"]


def upsert_job_posting(conn, job, company_id, crawl_run_id, source):
    duplicate_key = make_duplicate_key(job)
    existing = _find_existing_posting(conn, source, duplicate_key)
    content_hash = _hash_job(job)

    if not existing:
        job_posting_id = _insert_job_posting(conn, job, company_id, source, duplicate_key)
        _insert_history(conn, job_posting_id, crawl_run_id, "new", job, content_hash, {})
        return "new"

    was_inactive = existing["status"] and existing["status"] != "active"
    changed_fields = _get_changed_fields(existing, job, company_id)
    job_posting_id = existing["id"]
    _update_job_posting(conn, job_posting_id, job, company_id, increment_reopen=was_inactive)

    if was_inactive:
        _insert_history(conn, job_posting_id, crawl_run_id, "reopened", job, content_hash, changed_fields)
        return "updated"

    if changed_fields:
        _insert_history(conn, job_posting_id, crawl_run_id, "changed", job, content_hash, changed_fields)
        return "updated"

    _insert_history(conn, job_posting_id, crawl_run_id, "seen", job, content_hash, {})
    return "unchanged"


def make_duplicate_key(job):
    job_id = _clean_text(job.get("job_id"))
    normalized_url = _clean_text(job.get("normalized_url")) or normalize_url(job.get("url", ""))

    if job_id:
        return f"job_id:{job_id}"
    if normalized_url:
        return f"url:{normalized_url}"

    fallback = "|".join(
        [
            _normalize_key(job.get("company")),
            _normalize_key(job.get("title")),
            _normalize_key(job.get("deadline")),
        ]
    )
    return f"fallback:{fallback}"


def _insert_job_posting(conn, job, company_id, source, duplicate_key):
    cursor = conn.execute(
        """
        INSERT INTO job_postings (
            source,
            source_job_id,
            duplicate_key,
            company_id,
            title,
            detail_url,
            normalized_url,
            summary_text,
            location,
            career,
            education,
            employment_type,
            salary_text,
            deadline,
            deadline_date,
            status,
            raw_summary_text,
            collected_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            source,
            _none_if_empty(job.get("job_id")),
            duplicate_key,
            company_id,
            _clean_text(job.get("title")),
            _clean_text(job.get("url")),
            _clean_text(job.get("normalized_url")),
            _clean_text(job.get("raw_text")),
            _clean_text(job.get("location")),
            _clean_text(job.get("career")),
            _clean_text(job.get("education")),
            _clean_text(job.get("employment_type")),
            _clean_text(job.get("salary")),
            _clean_text(job.get("deadline")),
            _resolve_deadline_date(job),
            "active",
            _clean_text(job.get("raw_text")),
        ),
    )
    return cursor.lastrowid


def _update_job_posting(conn, job_posting_id, job, company_id, increment_reopen=False):
    conn.execute(
        """
        UPDATE job_postings
        SET
            company_id = ?,
            title = ?,
            detail_url = ?,
            normalized_url = ?,
            summary_text = ?,
            location = ?,
            career = ?,
            education = ?,
            employment_type = ?,
            salary_text = ?,
            deadline = ?,
            deadline_date = ?,
            status = 'active',
            reopen_count = reopen_count + ?,
            raw_summary_text = ?,
            last_seen_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP,
            collected_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            company_id,
            _clean_text(job.get("title")),
            _clean_text(job.get("url")),
            _clean_text(job.get("normalized_url")),
            _clean_text(job.get("raw_text")),
            _clean_text(job.get("location")),
            _clean_text(job.get("career")),
            _clean_text(job.get("education")),
            _clean_text(job.get("employment_type")),
            _clean_text(job.get("salary")),
            _clean_text(job.get("deadline")),
            _resolve_deadline_date(job),
            1 if increment_reopen else 0,
            _clean_text(job.get("raw_text")),
            job_posting_id,
        ),
    )


def _insert_history(conn, job_posting_id, crawl_run_id, status, job, content_hash, changed_fields):
    conn.execute(
        """
        INSERT INTO posting_history (
            job_posting_id,
            crawl_run_id,
            status,
            title_snapshot,
            deadline_snapshot,
            salary_snapshot,
            company_snapshot,
            content_hash,
            changed_fields_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_posting_id,
            crawl_run_id,
            status,
            _clean_text(job.get("title")),
            _clean_text(job.get("deadline")),
            _clean_text(job.get("salary")),
            _clean_text(job.get("company")),
            content_hash,
            json.dumps(changed_fields, ensure_ascii=False),
        ),
    )


def _find_existing_posting(conn, source, duplicate_key):
    return conn.execute(
        """
        SELECT *
        FROM job_postings
        WHERE source = ? AND duplicate_key = ?
        """,
        (source, duplicate_key),
    ).fetchone()


def _get_changed_fields(existing, job, company_id):
    field_map = {
        "company_id": company_id,
        "title": _clean_text(job.get("title")),
        "detail_url": _clean_text(job.get("url")),
        "normalized_url": _clean_text(job.get("normalized_url")),
        "location": _clean_text(job.get("location")),
        "summary_text": _clean_text(job.get("raw_text")),
        "salary_text": _clean_text(job.get("salary")),
        "deadline": _clean_text(job.get("deadline")),
        "deadline_date": _resolve_deadline_date(job),
    }

    changed = {}
    for field_name, new_value in field_map.items():
        old_value = existing[field_name]
        if old_value != new_value:
            changed[field_name] = {
                "old": old_value,
                "new": new_value,
            }

    return changed


def _is_valid_job(job):
    return bool(_clean_text(job.get("title")) and make_duplicate_key(job))


def _hash_job(job):
    payload = {
        "job_id": _clean_text(job.get("job_id")),
        "title": _clean_text(job.get("title")),
        "company": _clean_text(job.get("company")),
        "location": _clean_text(job.get("location")),
        "url": _clean_text(job.get("url")),
        "raw_text": _clean_text(job.get("raw_text")),
    }
    return _hash_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _hash_text(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _clean_text(value):
    return str(value).strip() if value is not None else ""


def _none_if_empty(value):
    cleaned = _clean_text(value)
    return cleaned or None


def _normalize_key(value):
    return " ".join(_clean_text(value).lower().split())


def _resolve_deadline_date(job):
    deadline = _clean_text(job.get("deadline"))
    if is_always_open_deadline(deadline):
        return None
    return _clean_text(job.get("deadline_date")) or normalize_deadline_date(deadline)


def backfill_deadline_dates(db_path=DEFAULT_DB_PATH):
    init_database(db_path)
    updated = 0
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, deadline
            FROM job_postings
            WHERE deadline IS NOT NULL
              AND deadline != ''
              AND (deadline_date IS NULL OR deadline_date = '')
            """
        ).fetchall()

        for row in rows:
            if is_always_open_deadline(row["deadline"]):
                continue
            deadline_date = normalize_deadline_date(row["deadline"])
            if not deadline_date:
                continue
            conn.execute(
                """
                UPDATE job_postings
                SET deadline_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (deadline_date, row["id"]),
            )
            updated += 1

    return updated
