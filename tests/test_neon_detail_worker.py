import unittest
from unittest.mock import Mock, patch

import httpx

from scripts.jobkorea_http import LIST_HEADERS
from scripts.neon_detail_worker import (
    HEADERS,
    RequestRateLimiter,
    fetch_detail,
    response_diagnostics,
)


class NeonDetailWorkerTests(unittest.TestCase):
    def test_detail_headers_include_browser_navigation_context(self):
        for name in (
            "User-Agent", "Accept", "Accept-Language", "Referer", "Origin",
            "Sec-CH-UA", "Sec-CH-UA-Mobile", "Sec-CH-UA-Platform",
            "Sec-Fetch-Dest", "Sec-Fetch-Mode", "Sec-Fetch-Site",
            "Upgrade-Insecure-Requests",
        ):
            self.assertIn(name, HEADERS)

    def test_list_and_detail_headers_share_browser_identity(self):
        for name in (
            "User-Agent", "Accept-Language", "Origin", "Referer",
            "Sec-CH-UA", "Sec-CH-UA-Mobile", "Sec-CH-UA-Platform",
            "Sec-Fetch-Site",
        ):
            self.assertEqual(HEADERS[name], LIST_HEADERS[name])

    def test_response_diagnostics_exposes_waf_clues(self):
        response = httpx.Response(
            403,
            text="  Access denied   by request blocked policy  ",
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://www.jobkorea.co.kr/Recruit/GI_Read/123"),
        )

        details = response_diagnostics(response)

        self.assertIn("status=403", details)
        self.assertIn("content_type=text/html", details)
        self.assertIn("access denied", details)
        self.assertIn("body_hint='Access denied by request blocked policy'", details)

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
        self.assertIn("status=200", str(result[3]))
        self.assertIn("body_hint='challenge'", str(result[3]))
        self.assertEqual(client.get.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
