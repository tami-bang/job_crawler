import json
import os
from pathlib import Path

from backend.db import open_database


FAVORITE_STATUSES = {
    "saved",
    "planned",
    "applied",
    "document_passed",
    "first_passed",
    "second_passed",
    "final_passed",
    "excluded",
}


def _parse_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    return parsed if isinstance(parsed, list) else [str(parsed)]


def _serialize_job(row):
    item = dict(row)
    item["match_score"] = round(item.get("match_score") or 0)
    item["matched_keywords"] = _parse_list(item.pop("matched_keywords_json", None))
    item["positive_reasons"] = _parse_list(item.pop("positive_reasons_json", None))
    item["negative_reasons"] = _parse_list(item.pop("negative_reasons_json", None))
    item["is_favorite"] = bool(item.get("favorite_id"))
    return item


def list_jobs(search=None, favorite_only=False, status=None, limit=100, job_id=None):
    where = ["1 = 1"]
    params = []

    if search:
        term = f"%{search.strip()}%"
        where.append("(jp.title LIKE ? OR c.name LIKE ? OR jp.skill_candidates LIKE ?)")
        params.extend([term, term, term])
    if favorite_only:
        where.append("fj.id IS NOT NULL")
    if status:
        where.append("fj.status = ?")
        params.append(status)
    if job_id is not None:
        where.append("jp.id = ?")
        params.append(job_id)

    hard_filters = _load_hard_filters()
    if hard_filters.get("strict_location_only") and hard_filters.get("locations"):
        location_clauses = []
        for location in hard_filters["locations"]:
            location_clauses.append("jp.location LIKE ?")
            params.append(f"%{location}%")
        where.append(f"({' OR '.join(location_clauses)})")

    params.append(max(1, min(limit, 500)))
    sql = f"""
        WITH latest_profile AS (
            SELECT id FROM user_profiles ORDER BY updated_at DESC, id DESC LIMIT 1
        )
        SELECT
            jp.id,
            jp.title,
            jp.location,
            jp.career,
            jp.education,
            jp.employment_type,
            jp.deadline,
            jp.deadline_date,
            jp.detail_url,
            jp.skill_candidates,
            jp.detail_status,
            c.name AS company_name,
            COALESCE(jmr.match_score, jmr.score, 0) AS match_score,
            jmr.recommendation_level,
            jmr.matched_keywords_json,
            jmr.positive_reasons_json,
            jmr.negative_reasons_json,
            jmr.reason,
            fj.id AS favorite_id,
            fj.memo AS favorite_memo,
            fj.status AS favorite_status
        FROM job_postings jp
        LEFT JOIN companies c ON c.id = jp.company_id
        LEFT JOIN latest_profile lp ON 1 = 1
        LEFT JOIN job_match_results jmr
          ON jmr.job_posting_id = jp.id AND jmr.user_profile_id = lp.id
        LEFT JOIN favorite_jobs fj ON fj.job_posting_id = jp.id
        WHERE {' AND '.join(where)}
        ORDER BY
            CASE WHEN fj.id IS NULL THEN 1 ELSE 0 END,
            COALESCE(jmr.match_score, jmr.score, 0) DESC,
            jp.updated_at DESC
        LIMIT ?
    """

    with open_database() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_serialize_job(row) for row in rows]


def get_job(job_id):
    jobs = list_jobs(limit=1, job_id=job_id)
    return jobs[0] if jobs else None


def save_favorite(job_id, memo="", status="saved"):
    _validate_status(status)
    with open_database() as conn:
        exists = conn.execute("SELECT 1 FROM job_postings WHERE id = ?", (job_id,)).fetchone()
        if not exists:
            raise LookupError("존재하지 않는 채용공고입니다.")
        conn.execute(
            """
            INSERT INTO favorite_jobs (job_posting_id, memo, status)
            VALUES (?, ?, ?)
            ON CONFLICT(job_posting_id) DO UPDATE SET
                memo = excluded.memo,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (job_id, memo.strip(), status),
        )
    return get_job(job_id)


def update_favorite(job_id, memo=None, status=None):
    if status is not None:
        _validate_status(status)
    with open_database() as conn:
        favorite = conn.execute(
            "SELECT memo, status FROM favorite_jobs WHERE job_posting_id = ?",
            (job_id,),
        ).fetchone()
        if not favorite:
            raise LookupError("관심공고로 저장되지 않은 공고입니다.")
        conn.execute(
            """
            UPDATE favorite_jobs
            SET memo = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_posting_id = ?
            """,
            (
                favorite["memo"] if memo is None else memo.strip(),
                favorite["status"] if status is None else status,
                job_id,
            ),
        )
    return get_job(job_id)


def delete_favorite(job_id):
    with open_database() as conn:
        deleted = conn.execute(
            "DELETE FROM favorite_jobs WHERE job_posting_id = ?",
            (job_id,),
        ).rowcount
    return bool(deleted)


def get_stats():
    with open_database() as conn:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM job_postings) AS total_jobs,
                (SELECT COUNT(*) FROM job_postings WHERE detail_status = 'success') AS detailed_jobs,
                (SELECT COUNT(DISTINCT job_posting_id) FROM job_match_results) AS matched_jobs,
                (SELECT COUNT(*) FROM favorite_jobs) AS favorite_jobs,
                (SELECT ROUND(AVG(COALESCE(match_score, score)), 1) FROM job_match_results) AS average_score
            """
        ).fetchone()
    return dict(row)


def _validate_status(status):
    if status not in FAVORITE_STATUSES:
        raise ValueError("지원 상태 값이 올바르지 않습니다.")


def _load_hard_filters():
    path = Path(os.getenv("JOB_RADAR_PREFERENCES_PATH", "config/user_preferences.json"))
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file).get("hard_filters", {})
    except (OSError, json.JSONDecodeError):
        return {}
