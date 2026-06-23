# crawler/database.py
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = "data/job_radar.db"


def get_connection(db_path=DEFAULT_DB_PATH):
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database(db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crawl_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                crawl_type TEXT NOT NULL,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                request_url TEXT,
                request_params_json TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS raw_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawl_run_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                page_type TEXT NOT NULL,
                url TEXT NOT NULL,
                raw_content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (crawl_run_id) REFERENCES crawl_runs(id)
            );

            CREATE TABLE IF NOT EXISTS taxonomy_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, code)
            );

            CREATE TABLE IF NOT EXISTS taxonomy_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                parent_id INTEGER,
                source TEXT NOT NULL,
                source_code TEXT,
                name TEXT NOT NULL,
                depth INTEGER NOT NULL DEFAULT 1,
                path TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES taxonomy_groups(id),
                FOREIGN KEY (parent_id) REFERENCES taxonomy_values(id),
                UNIQUE(group_id, path)
            );

            CREATE TABLE IF NOT EXISTS taxonomy_value_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                taxonomy_value_id INTEGER NOT NULL,
                crawl_run_id INTEGER NOT NULL,
                posting_count INTEGER,
                observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (taxonomy_value_id) REFERENCES taxonomy_values(id),
                FOREIGN KEY (crawl_run_id) REFERENCES crawl_runs(id)
            );

            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_company_key TEXT,
                name TEXT NOT NULL,
                company_url TEXT,
                company_type_taxonomy_id INTEGER,
                primary_industry_taxonomy_id INTEGER,
                raw_metadata_json TEXT,
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_type_taxonomy_id) REFERENCES taxonomy_values(id),
                FOREIGN KEY (primary_industry_taxonomy_id) REFERENCES taxonomy_values(id),
                UNIQUE(source, source_company_key)
            );

            CREATE TABLE IF NOT EXISTS job_postings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_job_id TEXT,
                company_id INTEGER,
                title TEXT NOT NULL,
                detail_url TEXT,
                summary_text TEXT,
                description_text TEXT,
                salary_text TEXT,
                posted_date TEXT,
                deadline TEXT,
                status TEXT NOT NULL DEFAULT 'unknown',
                raw_summary_text TEXT,
                raw_detail_text TEXT,
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id),
                UNIQUE(source, source_job_id)
            );

            CREATE TABLE IF NOT EXISTS job_posting_taxonomy_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_posting_id INTEGER NOT NULL,
                taxonomy_value_id INTEGER NOT NULL,
                relation_type TEXT NOT NULL,
                source_field TEXT,
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
                FOREIGN KEY (taxonomy_value_id) REFERENCES taxonomy_values(id),
                UNIQUE(job_posting_id, taxonomy_value_id, relation_type)
            );

            CREATE TABLE IF NOT EXISTS posting_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_posting_id INTEGER NOT NULL,
                crawl_run_id INTEGER NOT NULL,
                observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                title_snapshot TEXT,
                deadline_snapshot TEXT,
                salary_snapshot TEXT,
                company_snapshot TEXT,
                content_hash TEXT,
                changed_fields_json TEXT,
                FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
                FOREIGN KEY (crawl_run_id) REFERENCES crawl_runs(id)
            );

            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_preference_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                preference_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_profile_id) REFERENCES user_profiles(id),
                UNIQUE(user_profile_id, keyword, preference_type)
            );

            CREATE TABLE IF NOT EXISTS user_preference_taxonomy_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                taxonomy_value_id INTEGER NOT NULL,
                preference_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_profile_id) REFERENCES user_profiles(id),
                FOREIGN KEY (taxonomy_value_id) REFERENCES taxonomy_values(id),
                UNIQUE(user_profile_id, taxonomy_value_id, preference_type)
            );

            CREATE TABLE IF NOT EXISTS job_match_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_profile_id INTEGER NOT NULL,
                job_posting_id INTEGER NOT NULL,
                score REAL NOT NULL,
                matched_taxonomy_json TEXT,
                missing_taxonomy_json TEXT,
                matched_keywords_json TEXT,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_profile_id) REFERENCES user_profiles(id),
                FOREIGN KEY (job_posting_id) REFERENCES job_postings(id)
            );

            CREATE TABLE IF NOT EXISTS favorite_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_posting_id INTEGER NOT NULL UNIQUE,
                memo TEXT,
                status TEXT NOT NULL DEFAULT 'saved',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_posting_id) REFERENCES job_postings(id) ON DELETE CASCADE,
                CHECK (status IN ('saved', 'planned', 'applied', 'excluded'))
            );
            """
        )
        _ensure_column(conn, "job_postings", "normalized_url", "TEXT")
        _ensure_column(conn, "job_postings", "duplicate_key", "TEXT")
        _ensure_column(conn, "job_postings", "location", "TEXT")
        _ensure_column(conn, "job_postings", "career", "TEXT")
        _ensure_column(conn, "job_postings", "education", "TEXT")
        _ensure_column(conn, "job_postings", "employment_type", "TEXT")
        _ensure_column(conn, "job_postings", "collected_at", "TEXT")
        _ensure_column(conn, "job_postings", "deadline_date", "TEXT")
        _ensure_column(conn, "job_postings", "main_tasks", "TEXT")
        _ensure_column(conn, "job_postings", "qualifications", "TEXT")
        _ensure_column(conn, "job_postings", "preferred_conditions", "TEXT")
        _ensure_column(conn, "job_postings", "benefits", "TEXT")
        _ensure_column(conn, "job_postings", "skill_candidates", "TEXT")
        _ensure_column(conn, "job_postings", "detail_collected_at", "TEXT")
        _ensure_column(conn, "job_postings", "detail_status", "TEXT")
        _ensure_column(conn, "job_postings", "detail_error", "TEXT")
        _ensure_column(conn, "job_postings", "reopen_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "job_match_results", "match_score", "REAL")
        _ensure_column(conn, "job_match_results", "raw_score", "REAL")
        _ensure_column(conn, "job_match_results", "missing_keywords_json", "TEXT")
        _ensure_column(conn, "job_match_results", "positive_reasons_json", "TEXT")
        _ensure_column(conn, "job_match_results", "negative_reasons_json", "TEXT")
        _ensure_column(conn, "job_match_results", "recommendation_level", "TEXT")
        _ensure_column(conn, "job_match_results", "updated_at", "TEXT")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_job_postings_source_duplicate_key
            ON job_postings(source, duplicate_key)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_posting_history_job_posting_id
            ON posting_history(job_posting_id)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_job_match_results_user_job
            ON job_match_results(user_profile_id, job_posting_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_favorite_jobs_status_updated
            ON favorite_jobs(status, updated_at DESC)
            """
        )


def _ensure_column(conn, table_name, column_name, column_type):
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_names = {column["name"] for column in columns}
    if column_name in existing_names:
        return

    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def start_crawl_run(source, crawl_type, request_url=None, request_params_json=None, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO crawl_runs (source, crawl_type, request_url, request_params_json)
            VALUES (?, ?, ?, ?)
            """,
            (source, crawl_type, request_url, request_params_json),
        )
        return cursor.lastrowid


def finish_crawl_run(crawl_run_id, status="success", error_message=None, db_path=DEFAULT_DB_PATH):
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE crawl_runs
            SET finished_at = CURRENT_TIMESTAMP,
                status = ?,
                error_message = ?
            WHERE id = ?
            """,
            (status, error_message, crawl_run_id),
        )
