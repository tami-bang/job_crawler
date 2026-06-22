import unittest

from crawler.fetcher import is_healthy_html


class FetcherHealthTests(unittest.TestCase):
    def test_accepts_normal_html(self):
        html = "<html><body>" + ("정상 채용 공고 " * 100) + "</body></html>"
        self.assertTrue(is_healthy_html(html, min_html_length=500))

    def test_rejects_short_html(self):
        self.assertFalse(is_healthy_html("<html></html>", min_html_length=500))

    def test_rejects_blocked_page(self):
        html = "<html><body>CAPTCHA " + ("blocked " * 100) + "</body></html>"
        self.assertFalse(is_healthy_html(html, min_html_length=500))


if __name__ == "__main__":
    unittest.main()
