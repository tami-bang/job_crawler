# crawler/health.py
from crawler.database import DEFAULT_DB_PATH, get_connection, init_database


DEFAULT_ALLOWED_LOCATION_PREFIXES = ("서울", "경기", "인천")


def build_collection_health_report(
    db_path=DEFAULT_DB_PATH,
    allowed_location_prefixes=DEFAULT_ALLOWED_LOCATION_PREFIXES,
):
    init_database(db_path)
    location_filter, location_params = build_location_filter(
        "location",
        allowed_location_prefixes,
    )

    with get_connection(db_path) as conn:
        metrics = {
            "total_job_postings": scalar(conn, "SELECT COUNT(1) FROM job_postings"),
            "active_region_jobs": scalar(
                conn,
                f"""
                SELECT COUNT(1)
                FROM job_postings
                WHERE source = 'jobkorea'
                  {location_filter}
                  AND (
                        deadline_date IS NULL
                        OR deadline_date = ''
                        OR deadline_date >= date('now', '+9 hours')
                      )
                """,
                location_params,
            ),
            "active_region_missing_deadline_date": scalar(
                conn,
                f"""
                SELECT COUNT(1)
                FROM job_postings
                WHERE source = 'jobkorea'
                  {location_filter}
                  AND (deadline_date IS NULL OR deadline_date = '')
                """,
                location_params,
            ),
            "active_region_detail_missing": scalar(
                conn,
                f"""
                SELECT COUNT(1)
                FROM job_postings
                WHERE source = 'jobkorea'
                  {location_filter}
                  AND (
                        deadline_date IS NULL
                        OR deadline_date = ''
                        OR deadline_date >= date('now', '+9 hours')
                      )
                  AND (
                        detail_collected_at IS NULL
                        OR detail_collected_at = ''
                        OR detail_status = 'failed'
                      )
                """,
                location_params,
            ),
            "duplicate_source_job_id_groups": scalar(
                conn,
                """
                SELECT COUNT(1)
                FROM (
                    SELECT source_job_id
                    FROM job_postings
                    WHERE source_job_id IS NOT NULL AND source_job_id != ''
                    GROUP BY source_job_id
                    HAVING COUNT(1) > 1
                )
                """,
            ),
            "latest_list_crawl_at": scalar(
                conn,
                """
                SELECT MAX(finished_at)
                FROM crawl_runs
                WHERE source = 'jobkorea'
                  AND crawl_type = 'list'
                  AND status = 'success'
                """,
            ),
            "latest_detail_crawl_at": scalar(
                conn,
                """
                SELECT MAX(finished_at)
                FROM crawl_runs
                WHERE source = 'jobkorea'
                  AND crawl_type = 'detail'
                  AND status = 'success'
                """,
            ),
        }

        metrics["recent_zero_job_keywords"] = [
            row["request_params_json"]
            for row in conn.execute(
                """
                SELECT request_params_json
                FROM crawl_runs
                WHERE source = 'jobkorea'
                  AND crawl_type = 'list'
                  AND status = 'success'
                ORDER BY id DESC
                LIMIT 20
                """
            ).fetchall()
        ]

    return metrics


def print_collection_health_report(metrics):
    print("[HEALTH] JobKorea collection quality")
    for key, value in metrics.items():
        if key == "recent_zero_job_keywords":
            continue
        print(f"  {key}={value}")


def scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def build_location_filter(column_name, allowed_location_prefixes):
    prefixes = [
        str(prefix).strip()
        for prefix in allowed_location_prefixes
        if str(prefix).strip()
    ]
    if not prefixes:
        return "", []

    clauses = [f"{column_name} LIKE ?" for _ in prefixes]
    params = [f"{prefix}%" for prefix in prefixes]
    return f"AND ({' OR '.join(clauses)})", params
