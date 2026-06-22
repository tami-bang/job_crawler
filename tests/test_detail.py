import json
import unittest

from crawler.detail import parse_job_detail


class JobKoreaDetailTests(unittest.TestCase):
    def test_extracts_job_fields_from_jobposting_jsonld(self):
        payload = {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "백엔드 개발자",
            "employmentType": "FULL_TIME",
            "experienceRequirements": "경력 3년 이상",
            "educationRequirements": "학력무관",
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressRegion": "경기",
                    "addressLocality": "성남시",
                },
            },
        }
        html = (
            "<html><head><script type='application/ld+json'>"
            + json.dumps(payload, ensure_ascii=False)
            + "</script></head><body><h1>백엔드 개발자</h1></body></html>"
        )

        result = parse_job_detail(html)

        self.assertEqual(result["employment_type"], "정규직")
        self.assertEqual(result["location"], "경기 성남시")
        self.assertEqual(result["career"], "경력 3년 이상")
        self.assertEqual(result["education"], "학력무관")

    def test_falls_back_to_visible_employment_label(self):
        html = "<html><body><div>고용형태\n계약직</div></body></html>"

        result = parse_job_detail(html)

        self.assertEqual(result["employment_type"], "계약직")

    def test_uses_street_address_when_region_fields_are_missing(self):
        payload = {
            "@type": "JobPosting",
            "employmentType": "FULL_TIME",
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "서울 강남구 테헤란로 1",
                },
            },
        }
        html = (
            "<script type='application/ld+json'>"
            + json.dumps(payload, ensure_ascii=False)
            + "</script>"
        )

        result = parse_job_detail(html)

        self.assertEqual(result["location"], "서울 강남구 테헤란로 1")


if __name__ == "__main__":
    unittest.main()
