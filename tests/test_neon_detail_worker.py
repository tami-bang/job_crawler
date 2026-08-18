import unittest
from unittest.mock import MagicMock, Mock, patch

import httpx

from scripts.jobkorea_http import LIST_HEADERS
from scripts.neon_detail_worker import (
    HEADERS,
    RequestRateLimiter,
    detect_waf_signals,
    fetch_detail,
    response_diagnostics,
    save_success,
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
            text="<html><head><title>Access Denied</title></head><body>blocked</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
            request=httpx.Request("GET", "https://www.jobkorea.co.kr/Recruit/GI_Read/123"),
        )

        details = response_diagnostics(response)

        self.assertIn("status=403", details)
        self.assertIn("content_type=text/html", details)
        self.assertIn("block_title:access denied", details)

    def test_waf_detection_ignores_forbidden_as_normal_body_word(self):
        html = "<html><head><title>개발자 채용</title></head><body>forbidden은 일반 설명 단어입니다.</body></html>"

        self.assertEqual(detect_waf_signals(html), [])

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

    @patch("scripts.neon_detail_worker.job_passes_hard_filters", return_value=False)
    def test_accepts_short_jsonld_detail_and_marks_queue_success(self, _passes_filters):
        description = "Python 기반 백엔드 서비스를 설계하고 운영하며 API 품질과 안정성을 지속적으로 개선합니다."
        html = (
            "<html><head><script type='application/ld+json'>"
            f"{{\"@type\": \"JobPosting\", \"description\": \"{description}\"}}"
            "</script></head><body></body></html>"
        )
        client = Mock()
        client.get.return_value = httpx.Response(
            200,
            text=html,
            request=httpx.Request("GET", "https://www.jobkorea.co.kr/Recruit/GI_Read/123"),
        )
        row = (1, "123", "백엔드 개발자", "회사", "{}")

        fetched_row, url, parsed, error = fetch_detail(row, client, RequestRateLimiter(0), 1)

        self.assertIsNone(error)
        self.assertEqual(parsed["body_source"], "json_ld")
        self.assertGreaterEqual(len(parsed["raw_detail_text"]), 50)

        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        save_success(conn, fetched_row, url, parsed, {})

        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn("detail_status='success'", cursor.execute.call_args_list[0].args[0])
        self.assertIn("status='SUCCESS'", cursor.execute.call_args_list[1].args[0])

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
