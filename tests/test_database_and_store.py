import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.database import init_database
from crawler.job_store import make_duplicate_key, save_job_list_items


class DatabaseAndStoreTests(unittest.TestCase):
    def test_duplicate_key_priority(self):
        self.assertEqual(make_duplicate_key({"job_id": "42"}), "job_id:42")
        self.assertEqual(
            make_duplicate_key({"url": "https://example.com/jobs/1?source=test"}),
            "url:https://example.com/jobs/1",
        )

    def test_repeated_job_is_not_inserted_twice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "jobs.db")
            init_database(db_path)
            with sqlite3.connect(db_path) as conn:
                match_columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(job_match_results)").fetchall()
                }
                self.assertIn("raw_score", match_columns)
                run_id = conn.execute(
                    "INSERT INTO crawl_runs (source, crawl_type) VALUES ('jobkorea', 'list')"
                ).lastrowid

            job = {
                "job_id": "100",
                "title": "백엔드 개발자",
                "company": "테스트 회사",
                "url": "https://example.com/Recruit/GI_Read/100",
                "normalized_url": "https://example.com/Recruit/GI_Read/100",
                "location": "서울",
                "career": "신입",
                "education": "학력무관",
                "employment_type": "정규직",
                "deadline": "2026-12-31",
                "raw_text": "테스트 공고",
            }

            first = save_job_list_items([job], run_id, db_path=db_path)
            second = save_job_list_items([job], run_id, db_path=db_path)

            self.assertEqual(first["new"], 1)
            self.assertEqual(second["unchanged"], 1)
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
            self.assertEqual(count, 1)

    def test_reopened_job_increments_reopen_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "jobs.db")
            init_database(db_path)
            with sqlite3.connect(db_path) as conn:
                run_id = conn.execute(
                    "INSERT INTO crawl_runs (source, crawl_type) VALUES ('jobkorea', 'list')"
                ).lastrowid

            job = {
                "job_id": "200",
                "title": "AI 서비스 개발자",
                "company": "테스트 회사",
                "url": "https://example.com/Recruit/GI_Read/200",
                "normalized_url": "https://example.com/Recruit/GI_Read/200",
                "deadline": "2026-12-31",
                "raw_text": "테스트 공고",
            }

            save_job_list_items([job], run_id, db_path=db_path)
            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE job_postings SET status = 'closed' WHERE source_job_id = '200'")

            result = save_job_list_items([job], run_id, db_path=db_path)

            self.assertEqual(result["updated"], 1)
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT status, reopen_count FROM job_postings WHERE source_job_id = '200'"
                ).fetchone()
            self.assertEqual(row[0], "active")
            self.assertEqual(row[1], 1)


if __name__ == "__main__":
    unittest.main()
