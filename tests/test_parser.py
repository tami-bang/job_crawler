import unittest
from datetime import date
from pathlib import Path

from crawler.parser import extract_job_id, normalize_deadline_date, normalize_url, parse_html


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_extract_job_id_supports_path_and_query(self):
        self.assertEqual(extract_job_id("https://example.com/Recruit/GI_Read/12345"), "12345")
        self.assertEqual(extract_job_id("https://example.com/view?GI_No=987"), "987")

    def test_normalize_url_removes_query_fragment_and_trailing_slash(self):
        url = "HTTPS://Example.COM/jobs/123/?tracking=yes#section"
        self.assertEqual(normalize_url(url), "https://example.com/jobs/123")

    def test_normalize_deadline_date_rolls_next_year_for_past_month(self):
        today = date(2026, 12, 20)
        self.assertEqual(normalize_deadline_date("01/15(목)", today=today), "2027-01-15")

    def test_parse_jobkorea_fixture(self):
        html = (FIXTURE_DIR / "jobkorea_list.html").read_text(encoding="utf-8")
        selectors = {
            "card": 'div[data-sentry-component="CardJob"]',
            "title": 'a[data-sentry-component="Title"]',
            "company": "",
            "location": '[data-sentry-component="GrayChip"] span.truncate',
            "url": 'a[data-sentry-component="Title"]',
        }

        jobs = parse_html(html, selectors, base_url="https://www.jobkorea.co.kr/Search/")

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], "12345678")
        self.assertEqual(jobs[0]["title"], "Python 백엔드 개발자")
        self.assertEqual(jobs[0]["company"], "테스트 주식회사")
        self.assertEqual(jobs[0]["location"], "서울 강남구")
        self.assertEqual(jobs[0]["career"], "신입")
        self.assertEqual(jobs[0]["employment_type"], "정규직")


if __name__ == "__main__":
    unittest.main()

