import os
import tempfile
import unittest
from pathlib import Path

from backend.services.job_service import (
    delete_favorite,
    get_stats,
    list_jobs,
    save_favorite,
    update_favorite,
)
from crawler.database import get_connection
from scripts.seed_demo_data import seed_demo_data


class BackendServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "api.db")
        self.previous_path = os.environ.get("JOB_RADAR_DB_PATH")
        os.environ["JOB_RADAR_DB_PATH"] = self.db_path
        seed_demo_data(self.db_path)

    def tearDown(self):
        if self.previous_path is None:
            os.environ.pop("JOB_RADAR_DB_PATH", None)
        else:
            os.environ["JOB_RADAR_DB_PATH"] = self.previous_path
        self.temp_dir.cleanup()

    def test_jobs_are_sorted_by_match_score(self):
        jobs = list_jobs()
        self.assertEqual(len(jobs), 6)
        self.assertGreater(jobs[0]["match_score"], jobs[-1]["match_score"])

    def test_favorite_lifecycle_and_stats(self):
        job_id = list_jobs()[0]["id"]
        saved = save_favorite(job_id, "포트폴리오 정리 후 지원", "planned")
        self.assertTrue(saved["is_favorite"])
        self.assertEqual(get_stats()["favorite_jobs"], 1)

        updated = update_favorite(job_id, status="applied")
        self.assertEqual(updated["favorite_status"], "applied")
        self.assertTrue(delete_favorite(job_id))
        self.assertEqual(list_jobs(favorite_only=True), [])

    def test_dashboard_excludes_jobs_outside_allowed_locations(self):
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO job_postings (
                    source, source_job_id, title, location, employment_type,
                    detail_status, detail_collected_at
                ) VALUES ('demo', 'busan-job', '부산 Python 개발자', '부산 해운대구', '정규직', 'success', CURRENT_TIMESTAMP)
                """
            )

        titles = [job["title"] for job in list_jobs()]
        self.assertNotIn("부산 Python 개발자", titles)


if __name__ == "__main__":
    unittest.main()
