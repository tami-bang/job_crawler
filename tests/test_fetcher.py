import unittest
from unittest.mock import MagicMock, patch

import crawler.fetcher as fetcher
from crawler.fetcher import is_healthy_html


class FetcherHealthTests(unittest.TestCase):
    def tearDown(self):
        fetcher.close_dynamic_driver()

    def test_accepts_normal_html(self):
        html = "<html><body>" + ("정상 채용 공고 " * 100) + "</body></html>"
        self.assertTrue(is_healthy_html(html, min_html_length=500))

    def test_rejects_short_html(self):
        self.assertFalse(is_healthy_html("<html></html>", min_html_length=500))

    def test_rejects_blocked_page(self):
        html = "<html><body>CAPTCHA " + ("blocked " * 100) + "</body></html>"
        self.assertFalse(is_healthy_html(html, min_html_length=500))

    @patch("crawler.fetcher.WebDriverWait")
    @patch("crawler.fetcher._create_dynamic_driver")
    def test_dynamic_driver_is_reused_between_requests(self, create_driver, wait):
        driver = MagicMock()
        driver.page_source = "<html>" + ("정상 공고 " * 100) + "</html>"
        create_driver.return_value = driver

        first = fetcher.fetch("https://example.com/1", dynamic=True, retries=1)
        second = fetcher.fetch("https://example.com/2", dynamic=True, retries=1)

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(create_driver.call_count, 1)
        self.assertEqual(driver.get.call_count, 2)
        wait.return_value.until.assert_called()

    @patch("crawler.fetcher.time.sleep")
    @patch("crawler.fetcher.WebDriverWait")
    @patch("crawler.fetcher._create_dynamic_driver")
    def test_failed_driver_is_closed_and_recreated(self, create_driver, wait, sleep):
        failed_driver = MagicMock()
        failed_driver.get.side_effect = RuntimeError("session lost")
        healthy_driver = MagicMock()
        healthy_driver.page_source = "<html>" + ("정상 공고 " * 100) + "</html>"
        create_driver.side_effect = [failed_driver, healthy_driver]

        html = fetcher.fetch("https://example.com", dynamic=True, retries=2)

        self.assertTrue(html)
        self.assertEqual(create_driver.call_count, 2)
        failed_driver.quit.assert_called_once()
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
