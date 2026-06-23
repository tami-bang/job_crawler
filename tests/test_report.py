import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.services.report_service import build_jobs_xlsx, validate_email_address
from crawler.report import export_match_report, export_xlsx_match_report, get_report_fieldnames


class ReportTests(unittest.TestCase):
    def test_csv_and_xlsx_exports_are_created(self):
        row = {field: "" for field in get_report_fieldnames()}
        row.update({"company": "테스트 회사", "job_title": "백엔드 개발자", "score": 88})

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "report.csv"
            export_match_report([row], csv_path)
            xlsx_path = Path(export_xlsx_match_report([row], csv_path))

            self.assertTrue(csv_path.exists())
            self.assertTrue(xlsx_path.exists())
            with csv_path.open(encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(rows[0]["company"], "테스트 회사")
            with zipfile.ZipFile(xlsx_path) as workbook:
                self.assertIn("xl/worksheets/sheet1.xml", workbook.namelist())

    def test_dashboard_xlsx_export_contains_korean_headers(self):
        workbook_bytes = build_jobs_xlsx([
            {
                "score": 91,
                "company": "테스트 회사",
                "job_title": "Python 백엔드 개발자",
                "location": "서울",
                "career": "신입",
                "employment_type": "정규직",
                "deadline": "2026-07-02",
                "matched_keywords": "Python, FastAPI",
                "reason": "선호 기술과 일치",
                "job_url": "https://example.com/jobs/1",
            }
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx_path = Path(temp_dir) / "dashboard.xlsx"
            xlsx_path.write_bytes(workbook_bytes)
            with zipfile.ZipFile(xlsx_path) as workbook:
                sheet = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")

        self.assertIn("매칭 점수", sheet)
        self.assertIn("Python 백엔드 개발자", sheet)

    def test_validate_email_address_rejects_invalid_address(self):
        self.assertEqual(validate_email_address("tami@example.com"), "tami@example.com")
        with self.assertRaises(ValueError):
            validate_email_address("not-an-email")


if __name__ == "__main__":
    unittest.main()
