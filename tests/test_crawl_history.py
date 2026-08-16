import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.crawl_history import KST, record_crawl_history


class CrawlHistoryTests(unittest.TestCase):
    def test_records_korean_weekday_and_kst_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "crawl_history.json"
            record_crawl_history(
                42,
                6843,
                path=path,
                crawled_at=datetime(2026, 8, 16, 9, 7, tzinfo=KST),
            )
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [{
                "date": "2026.08.16",
                "day_of_week": "일",
                "new_jobs_count": 42,
                "total_jobs_count": 6843,
                "crawled_at": "09:07 KST",
            }])

    def test_same_day_runs_accumulate_and_dates_stay_latest_first(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "crawl_history.json"
            record_crawl_history(2, 6801, path=path, crawled_at=datetime(2026, 8, 15, 9, 5, tzinfo=KST))
            record_crawl_history(40, 6841, path=path, crawled_at=datetime(2026, 8, 16, 9, 7, tzinfo=KST))
            record_crawl_history(2, 6843, path=path, crawled_at=datetime(2026, 8, 16, 10, 30, tzinfo=KST))
            history = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual([entry["date"] for entry in history], ["2026.08.16", "2026.08.15"])
            self.assertEqual(history[0]["new_jobs_count"], 42)
            self.assertEqual(history[0]["total_jobs_count"], 6843)
            self.assertEqual(history[0]["crawled_at"], "10:30 KST")


if __name__ == "__main__":
    unittest.main()
