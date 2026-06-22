import unittest
from unittest.mock import patch

from main import fetch_list_jobs


class MainCollectionTests(unittest.TestCase):
    @patch("main.parse_html")
    @patch("main.fetch")
    @patch("main.fetch_list_page")
    def test_uses_selenium_when_static_collection_fails(
        self,
        fetch_list_page,
        fetch,
        parse_html,
    ):
        site = {
            "dynamic": True,
            "selectors": {"card": ".job-card"},
        }
        fetch_list_page.return_value = None
        fetch.return_value = "<html>dynamic result</html>"
        parse_html.return_value = [{"title": "백엔드 개발자"}]

        html, jobs = fetch_list_jobs(
            "jobkorea",
            site,
            "https://example.com/jobs",
        )

        self.assertEqual(html, "<html>dynamic result</html>")
        self.assertEqual(jobs, [{"title": "백엔드 개발자"}])
        fetch.assert_called_once_with(
            "https://example.com/jobs",
            dynamic=True,
            wait_selector=".job-card",
        )


if __name__ == "__main__":
    unittest.main()
