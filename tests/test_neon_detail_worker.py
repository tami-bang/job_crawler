import unittest
from unittest.mock import Mock, patch

import httpx

from scripts.neon_detail_worker import HEADERS, RequestRateLimiter, fetch_detail


class NeonDetailWorkerTests(unittest.TestCase):
    def test_detail_headers_include_browser_navigation_context(self):
        for name in (
            "User-Agent", "Accept", "Accept-Language", "Referer", "Origin",
            "Sec-CH-UA", "Sec-CH-UA-Mobile", "Sec-CH-UA-Platform",
            "Sec-Fetch-Dest", "Sec-Fetch-Mode", "Sec-Fetch-Site",
            "Upgrade-Insecure-Requests",
        ):
            self.assertIn(name, HEADERS)

    @patch("scripts.neon_detail_worker.time.sleep")
    @patch("scripts.neon_detail_worker.parse_job_detail")
    def test_retries_waf_response_then_succeeds(self, parse_detail, sleep):
        row = (1, "123", "title", "company", "{}")
        blocked = httpx.Response(
            403,
            request=httpx.Request("GET", "https://www.jobkorea.co.kr/Recruit/GI_Read/123"),
        )
        success = httpx.Response(
            200,
            text="detail",
            request=httpx.Request("GET", "https://www.jobkorea.co.kr/Recruit/GI_Read/123"),
        )
        client = Mock()
        client.get.side_effect = [blocked, success]
        parse_detail.return_value = {"has_core_content": True, "raw_detail_text": "x" * 120}

        result = fetch_detail(row, client, RequestRateLimiter(0), max_attempts=5)

        self.assertIsNone(result[3])
        self.assertEqual(client.get.call_count, 2)
        sleep.assert_called_once()

    @patch("scripts.neon_detail_worker.time.sleep")
    @patch("scripts.neon_detail_worker.parse_job_detail")
    def test_retries_invalid_waf_challenge_body(self, parse_detail, sleep):
        row = (1, "123", "title", "company", "{}")
        client = Mock()
        client.get.return_value = httpx.Response(
            200,
            text="challenge",
            request=httpx.Request("GET", "https://www.jobkorea.co.kr/Recruit/GI_Read/123"),
        )
        parse_detail.return_value = {"has_core_content": False, "raw_detail_text": ""}

        result = fetch_detail(row, client, RequestRateLimiter(0), max_attempts=3)

        self.assertIsInstance(result[3], RuntimeError)
        self.assertEqual(client.get.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
