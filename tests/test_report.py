import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()

